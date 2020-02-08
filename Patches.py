import itertools
import random
import re
import struct

from Hints import getSimpleHintNoPrefix
from Messages import update_message_by_id, shuffle_messages

NUM_VANILLA_OBJECTS = 0x192


def add_to_extended_object_table(rom, object_id, object_file):
    extended_id = object_id - NUM_VANILLA_OBJECTS - 1
    extended_object_table = rom.sym('EXTENDED_OBJECT_TABLE')
    rom.write_int32s(extended_object_table + extended_id * 8, [object_file.start, object_file.end])


item_row_struct = struct.Struct('>BBHHBBIIhh')  # Match item_row_t in item_table.h
item_row_fields = [
    'base_item_id', 'action_id', 'text_id', 'object_id', 'graphic_id', 'chest_type',
    'upgrade_fn', 'effect_fn', 'effect_arg1', 'effect_arg2',
]


def read_rom_item(rom, item_id):
    addr = rom.sym('item_table') + (item_id * item_row_struct.size)
    row_bytes = rom.read_bytes(addr, item_row_struct.size)
    row = item_row_struct.unpack(row_bytes)
    return {item_row_fields[i]: row[i] for i in range(len(item_row_fields))}


def write_rom_item(rom, item_id, item):
    addr = rom.sym('item_table') + (item_id * item_row_struct.size)
    row = [item[f] for f in item_row_fields]
    row_bytes = item_row_struct.pack(*row)
    rom.write_bytes(addr, row_bytes)


def get_override_table(world):
    return list(filter(lambda val: val != None, map(get_override_entry, world.get_filled_locations())))


override_struct = struct.Struct('>xBBBHBB')  # match override_t in get_items.c


def get_override_table_bytes(override_table):
    return b''.join(sorted(itertools.starmap(override_struct.pack, override_table)))


def get_override_entry(location):
    scene = location.scene
    default = location.default
    item_id = location.item.index
    if None in [scene, default, item_id]:
        return None

    player_id = location.item.world_id + 1
    if location.item.looks_like_item is not None:
        looks_like_item_id = location.item.looks_like_item.index
    else:
        looks_like_item_id = 0

    if location.type in ['NPC', 'BossHeart']:
        type = 0
    elif location.type == 'Chest':
        type = 1
        default &= 0x1F
    elif location.type == 'Collectable':
        type = 2
    elif location.type == 'GS Token':
        type = 3
    elif location.type == 'Shop' and location.item.type != 'Shop':
        type = 0
    elif location.type == 'GrottoNPC' and location.item.type != 'Shop':
        type = 4
    elif location.type in ['Song', 'Cutscene']:
        type = 5
    else:
        return None

    return (scene, type, default, item_id, player_id, looks_like_item_id)


chestTypeMap = {
    #    small   big     boss
    0x0000: [0x5000, 0x0000, 0x2000],  # Large
    0x1000: [0x7000, 0x1000, 0x1000],  # Large, Appears, Clear Flag
    0x2000: [0x5000, 0x0000, 0x2000],  # Boss Key’s Chest
    0x3000: [0x8000, 0x3000, 0x3000],  # Large, Falling, Switch Flag
    0x4000: [0x6000, 0x4000, 0x4000],  # Large, Invisible
    0x5000: [0x5000, 0x0000, 0x2000],  # Small
    0x6000: [0x6000, 0x4000, 0x4000],  # Small, Invisible
    0x7000: [0x7000, 0x1000, 0x1000],  # Small, Appears, Clear Flag
    0x8000: [0x8000, 0x3000, 0x3000],  # Small, Falling, Switch Flag
    0x9000: [0x9000, 0x9000, 0x9000],  # Large, Appears, Zelda's Lullaby
    0xA000: [0xA000, 0xA000, 0xA000],  # Large, Appears, Sun's Song Triggered
    0xB000: [0xB000, 0xB000, 0xB000],  # Large, Appears, Switch Flag
    0xC000: [0x5000, 0x0000, 0x2000],  # Large
    0xD000: [0x5000, 0x0000, 0x2000],  # Large
    0xE000: [0x5000, 0x0000, 0x2000],  # Large
    0xF000: [0x5000, 0x0000, 0x2000],  # Large
}


def room_get_actors(rom, actor_func, room_data, scene, alternate=None):
    actors = {}
    room_start = alternate if alternate else room_data
    command = 0
    while command != 0x14:  # 0x14 = end header
        command = rom.read_byte(room_data)
        if command == 0x01:  # actor list
            actor_count = rom.read_byte(room_data + 1)
            actor_list = room_start + (rom.read_int32(room_data + 4) & 0x00FFFFFF)
            for _ in range(0, actor_count):
                actor_id = rom.read_int16(actor_list)
                entry = actor_func(rom, actor_id, actor_list, scene)
                if entry:
                    actors[actor_list] = entry
                actor_list = actor_list + 16
        if command == 0x18:  # Alternate header list
            header_list = room_start + (rom.read_int32(room_data + 4) & 0x00FFFFFF)
            for alt_id in range(0, 3):
                header_data = room_start + (rom.read_int32(header_list) & 0x00FFFFFF)
                if header_data != 0 and not alternate:
                    actors.update(room_get_actors(rom, actor_func, header_data, scene, room_start))
                header_list = header_list + 4
        room_data = room_data + 8
    return actors


def scene_get_actors(rom, actor_func, scene_data, scene, alternate=None, processed_rooms=None):
    if processed_rooms == None:
        processed_rooms = []
    actors = {}
    scene_start = alternate if alternate else scene_data
    command = 0
    while command != 0x14:  # 0x14 = end header
        command = rom.read_byte(scene_data)
        if command == 0x04:  # room list
            room_count = rom.read_byte(scene_data + 1)
            room_list = scene_start + (rom.read_int32(scene_data + 4) & 0x00FFFFFF)
            for _ in range(0, room_count):
                room_data = rom.read_int32(room_list);

                if not room_data in processed_rooms:
                    actors.update(room_get_actors(rom, actor_func, room_data, scene))
                    processed_rooms.append(room_data)
                room_list = room_list + 8
        if command == 0x0E:  # transition actor list
            actor_count = rom.read_byte(scene_data + 1)
            actor_list = scene_start + (rom.read_int32(scene_data + 4) & 0x00FFFFFF)
            for _ in range(0, actor_count):
                actor_id = rom.read_int16(actor_list + 4)
                entry = actor_func(rom, actor_id, actor_list, scene)
                if entry:
                    actors[actor_list] = entry
                actor_list = actor_list + 16
        if command == 0x18:  # Alternate header list
            header_list = scene_start + (rom.read_int32(scene_data + 4) & 0x00FFFFFF)
            for alt_id in range(0, 3):
                header_data = scene_start + (rom.read_int32(header_list) & 0x00FFFFFF)
                if header_data != 0 and not alternate:
                    actors.update(scene_get_actors(rom, actor_func, header_data, scene, scene_start, processed_rooms))
                header_list = header_list + 4

        scene_data = scene_data + 8
    return actors


def get_actor_list(rom, actor_func):
    actors = {}
    scene_table = 0x00B71440
    for scene in range(0x00, 0x65):
        scene_data = rom.read_int32(scene_table + (scene * 0x14));
        actors.update(scene_get_actors(rom, actor_func, scene_data, scene))
    return actors


def get_override_itemid(override_table, scene, type, flags):
    for entry in override_table:
        if entry[0] == scene and (entry[1] & 0x07) == type and entry[2] == flags:
            return entry[4]
    return None


def remove_entrance_blockers(rom):
    def remove_entrance_blockers_do(rom, actor_id, actor, scene):
        if actor_id == 0x014E and scene == 97:
            actor_var = rom.read_int16(actor + 14);
            if actor_var == 0xFF01:
                rom.write_int16(actor + 14, 0x0700)

    get_actor_list(rom, remove_entrance_blockers_do)


def set_cow_id_data(rom, world):
    def set_cow_id(rom, actor_id, actor, scene):
        nonlocal last_scene
        nonlocal cow_count
        nonlocal last_actor

        if actor_id == 0x01C6:  # Cow
            if scene == last_scene and last_actor != actor:
                cow_count += 1
            else:
                cow_count = 1

            last_scene = scene
            last_actor = actor
            if world.dungeon_mq['Jabu Jabus Belly'] and scene == 2:  # If its an MQ jabu cow
                rom.write_int16(actor + 0x8, 1 if cow_count == 17 else 0)  # Give all wall cows ID 0, and set cow 11's ID to 1
            else:
                rom.write_int16(actor + 0x8, cow_count)

    last_actor = -1
    last_scene = -1
    cow_count = 1

    get_actor_list(rom, set_cow_id)


def set_grotto_shuffle_data(rom, world):
    def override_grotto_data(rom, actor_id, actor, scene):
        if actor_id == 0x009B:  # Grotto
            actor_zrot = rom.read_int16(actor + 12)
            actor_var = rom.read_int16(actor + 14)
            grotto_type = (actor_var >> 8) & 0x0F
            grotto_id = (scene << 8) + (actor_var & 0x00FF)

            rom.write_int16(actor + 12, grotto_entrances_override[grotto_id])
            rom.write_byte(actor + 14, grotto_type + 0x20)

    # Build the override table based on shuffled grotto entrances
    grotto_entrances_override = {}
    for entrance in world.get_shuffled_entrances(type='Grotto'):
        if entrance.primary:
            grotto_id = (entrance.data['scene'] << 8) + entrance.data['content']
            if entrance.replaces.type == 'Grotto':
                grotto_entrances_override[grotto_id] = 0x1000 + entrance.replaces.data['grotto_id']
            else:
                grotto_entrances_override[grotto_id] = entrance.replaces.data['index']
        else:
            exit_index = entrance.replaces.data.get('index', 0x7FFF)
            rom.write_int16(rom.sym('GROTTO_EXIT_LIST') + 2 * entrance.data['grotto_id'], exit_index)

    # Override grotto actors data with the new data
    get_actor_list(rom, override_grotto_data)


def set_deku_salesman_data(rom):
    def set_deku_salesman(rom, actor_id, actor, scene):
        if actor_id == 0x0195:  # Salesman
            actor_var = rom.read_int16(actor + 14)
            if actor_var == 6:
                rom.write_int16(actor + 14, 0x0003)

    get_actor_list(rom, set_deku_salesman)


def get_locked_doors(rom, world):
    def locked_door(rom, actor_id, actor, scene):
        actor_var = rom.read_int16(actor + 14)
        actor_type = actor_var >> 6
        actor_flag = actor_var & 0x003F

        flag_id = (1 << actor_flag)
        flag_byte = 3 - (actor_flag >> 3)
        flag_bits = 1 << (actor_flag & 0x07)

        # If locked door, set the door's unlock flag
        if world.shuffle_smallkeys == 'remove':
            if actor_id == 0x0009 and actor_type == 0x02:
                return [0x00D4 + scene * 0x1C + 0x04 + flag_byte, flag_bits]
            if actor_id == 0x002E and actor_type == 0x0B:
                return [0x00D4 + scene * 0x1C + 0x04 + flag_byte, flag_bits]

        # If boss door, set the door's unlock flag
        if (world.shuffle_bosskeys == 'remove' and scene != 0x0A) or (world.shuffle_ganon_bosskey == 'remove' and scene == 0x0A):
            if actor_id == 0x002E and actor_type == 0x05:
                return [0x00D4 + scene * 0x1C + 0x04 + flag_byte, flag_bits]

    return get_actor_list(rom, locked_door)


def create_fake_name(name):
    vowels = 'aeiou'
    list_name = list(name)
    vowel_indexes = [i for i, c in enumerate(list_name) if c in vowels]
    for i in random.sample(vowel_indexes, min(2, len(vowel_indexes))):
        c = list_name[i]
        list_name[i] = random.choice([v for v in vowels if v != c])

    # keeping the game E...
    new_name = ''.join(list_name)
    censor = ['cum', 'cunt', 'dike', 'penis', 'puss', 'shit']
    new_name_az = re.sub(r'[^a-zA-Z]', '', new_name.lower(), re.UNICODE)
    for cuss in censor:
        if cuss in new_name_az:
            return create_fake_name(name)
    return new_name


def place_shop_items(rom, world, shop_items, messages, locations, init_shop_id=False):
    if init_shop_id:
        place_shop_items.shop_id = 0x32

    shop_objs = {0x0148}  # "Sold Out" object
    for location in locations:
        if location.item.type == 'Shop':
            shop_objs.add(location.item.special['object'])
            rom.write_int16(location.address, location.item.index)
        else:
            if location.item.looks_like_item is not None:
                item_display = location.item.looks_like_item
            else:
                item_display = location.item

            # bottles in shops should look like empty bottles
            # so that that are different than normal shop refils
            if 'shop_object' in item_display.special:
                rom_item = read_rom_item(rom, item_display.special['shop_object'])
            else:
                rom_item = read_rom_item(rom, item_display.index)

            shop_objs.add(rom_item['object_id'])
            shop_id = place_shop_items.shop_id
            rom.write_int16(location.address, shop_id)
            shop_item = shop_items[shop_id]

            shop_item.object = rom_item['object_id']
            shop_item.model = rom_item['graphic_id'] - 1
            shop_item.price = location.price
            shop_item.pieces = 1
            shop_item.get_item_id = location.default
            shop_item.func1 = 0x808648CC
            shop_item.func2 = 0x808636B8
            shop_item.func3 = 0x00000000
            shop_item.func4 = 0x80863FB4

            message_id = (shop_id - 0x32) * 2
            shop_item.description_message = 0x8100 + message_id
            shop_item.purchase_message = 0x8100 + message_id + 1

            shuffle_messages.shop_item_messages.extend(
                [shop_item.description_message, shop_item.purchase_message])

            if item_display.dungeonitem:
                split_item_name = item_display.name.split('(')
                split_item_name[1] = '(' + split_item_name[1]

                if location.item.name == 'Ice Trap':
                    split_item_name[0] = create_fake_name(split_item_name[0])

                if world.world_count > 1:
                    description_text = '\x08\x05\x41%s  %d Rupees\x01%s\x01\x05\x42Player %d\x05\x40\x01Special deal! ONE LEFT!\x09\x0A\x02' % (
                    split_item_name[0], location.price, split_item_name[1], location.item.world_id + 1)
                else:
                    description_text = '\x08\x05\x41%s  %d Rupees\x01%s\x01\x05\x40Special deal! ONE LEFT!\x01Get it while it lasts!\x09\x0A\x02' % (
                    split_item_name[0], location.price, split_item_name[1])
                purchase_text = '\x08%s  %d Rupees\x09\x01%s\x01\x1B\x05\x42Buy\x01Don\'t buy\x05\x40\x02' % (split_item_name[0], location.price, split_item_name[1])
            else:
                shop_item_name = getSimpleHintNoPrefix(item_display)
                if location.item.name == 'Ice Trap':
                    shop_item_name = create_fake_name(shop_item_name)

                if world.world_count > 1:
                    description_text = '\x08\x05\x41%s  %d Rupees\x01\x05\x42Player %d\x05\x40\x01Special deal! ONE LEFT!\x09\x0A\x02' % (shop_item_name, location.price, location.item.world_id + 1)
                else:
                    description_text = '\x08\x05\x41%s  %d Rupees\x01\x05\x40Special deal! ONE LEFT!\x01Get it while it lasts!\x09\x0A\x02' % (shop_item_name, location.price)
                purchase_text = '\x08%s  %d Rupees\x09\x01\x01\x1B\x05\x42Buy\x01Don\'t buy\x05\x40\x02' % (shop_item_name, location.price)

            update_message_by_id(messages, shop_item.description_message, description_text, 0x03)
            update_message_by_id(messages, shop_item.purchase_message, purchase_text, 0x03)

            place_shop_items.shop_id += 1

    return shop_objs


def boss_reward_index(world, boss_name):
    code = world.get_location(boss_name).item.special['item_id']
    if code >= 0x6C:
        return code - 0x6C
    else:
        return 3 + code - 0x66


def configure_dungeon_info(rom, world):
    mq_enable = (world.mq_dungeons_random or world.mq_dungeons != 0 and world.mq_dungeons != 12)
    mapcompass_keysanity = world.settings.enhance_map_compass

    bosses = ['Queen Gohma', 'King Dodongo', 'Barinade', 'Phantom Ganon',
              'Volvagia', 'Morpha', 'Twinrova', 'Bongo Bongo']
    dungeon_rewards = [boss_reward_index(world, boss) for boss in bosses]

    codes = ['Deku Tree', 'Dodongos Cavern', 'Jabu Jabus Belly', 'Forest Temple',
             'Fire Temple', 'Water Temple', 'Spirit Temple', 'Shadow Temple',
             'Bottom of the Well', 'Ice Cavern', 'Tower (N/A)',
             'Gerudo Training Grounds', 'Hideout (N/A)', 'Ganons Castle']
    dungeon_is_mq = [1 if world.dungeon_mq.get(c) else 0 for c in codes]

    rom.write_int32(rom.sym('cfg_dungeon_info_enable'), 1)
    rom.write_int32(rom.sym('cfg_dungeon_info_mq_enable'), int(mq_enable))
    rom.write_int32(rom.sym('cfg_dungeon_info_mq_need_map'), int(mapcompass_keysanity))
    rom.write_int32(rom.sym('cfg_dungeon_info_reward_need_compass'), int(mapcompass_keysanity))
    rom.write_int32(rom.sym('cfg_dungeon_info_reward_need_altar'), int(not mapcompass_keysanity))
    rom.write_bytes(rom.sym('cfg_dungeon_rewards'), dungeon_rewards)
    rom.write_bytes(rom.sym('cfg_dungeon_is_mq'), dungeon_is_mq)
