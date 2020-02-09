import random
import struct
import itertools
import random
import re
import zlib

from World import World
from Rom import Rom
from Spoiler import Spoiler
from Utils import data_path
from OcarinaSongs import replace_songs
from MQ import patch_files, File, update_dmadata, insert_space, add_relocations
from SaveContext import SaveContext


def patch_rom(spoiler:Spoiler, world:World, rom:Rom):
    with open(data_path('generated/rom_patch.txt'), 'r') as stream:
        for line in stream:
            address, value = [int(x, 16) for x in line.split(',')]
            rom.write_int32(address, value)
    rom.scan_dmadata_update()

    # Write Randomizer title screen logo
    with open(data_path('title.bin'), 'rb') as stream:
        writeAddress = 0x01795300
        titleBytesComp = stream.read()
        titleBytesDiff = zlib.decompress(titleBytesComp)

        originalBytes = rom.original.buffer[writeAddress: writeAddress+ len(titleBytesDiff)]
        titleBytes = bytearray([a ^ b for a, b in zip(titleBytesDiff, originalBytes)])
        rom.write_bytes(writeAddress, titleBytes)

    # Fixes the typo of keatan mask in the item select screen
    with open(data_path('keaton.bin'), 'rb') as stream:
        writeAddress = 0x8A7C00
        keatonBytesComp = stream.read()
        keatonBytesDiff = zlib.decompress(keatonBytesComp)

        originalBytes = rom.original.buffer[writeAddress: writeAddress+ len(keatonBytesDiff)]
        keatonBytes = bytearray([a ^ b for a, b in zip(keatonBytesDiff, originalBytes)])
        rom.write_bytes(writeAddress, keatonBytes)

    # Load Triforce model into a file
    triforce_obj_file = File({ 'Name': 'object_gi_triforce' })
    triforce_obj_file.copy(rom)
    with open(data_path('triforce.bin'), 'rb') as stream:
        obj_data = stream.read()
        rom.write_bytes(triforce_obj_file.start, obj_data)
        triforce_obj_file.end = triforce_obj_file.start + len(obj_data)
    update_dmadata(rom, triforce_obj_file)
    # Add it to the extended object table
    add_to_extended_object_table(rom, 0x193, triforce_obj_file)

    # Build a Double Defense model from the Heart Container model
    dd_obj_file = File({
        'Name': 'object_gi_hearts',
        'Start': '014D9000',
        'End': '014DA590',
    })
    dd_obj_file.copy(rom)
    # Update colors for the Double Defense variant
    rom.write_bytes(dd_obj_file.start + 0x1294, [0xFF, 0xCF, 0x0F]) # Exterior Primary Color
    rom.write_bytes(dd_obj_file.start + 0x12B4, [0xFF, 0x46, 0x32]) # Exterior Env Color
    rom.write_int32s(dd_obj_file.start + 0x12A8, [0xFC173C60, 0x150C937F]) # Exterior Combine Mode
    rom.write_bytes(dd_obj_file.start + 0x1474, [0xFF, 0xFF, 0xFF]) # Interior Primary Color
    rom.write_bytes(dd_obj_file.start + 0x1494, [0xFF, 0xFF, 0xFF]) # Interior Env Color
    update_dmadata(rom, dd_obj_file)
    # Add it to the extended object table
    add_to_extended_object_table(rom, 0x194, dd_obj_file)

    # Force language to be English in the event a Japanese rom was submitted
    rom.write_byte(0x3E, 0x45)
    rom.force_patch.append(0x3E)

    # Increase the instance size of Bombchus prevent the heap from becoming corrupt when
    # a Dodongo eats a Bombchu. Does not fix stale pointer issues with the animation
    rom.write_int32(0xD6002C, 0x1F0)

    # Can always return to youth
    rom.write_byte(0xCB6844, 0x35)
    rom.write_byte(0x253C0E2, 0x03) # Moves sheik from pedestal

    # Fix Ice Cavern Alcove Camera
    if not world.dungeon_mq['Ice Cavern']:
        rom.write_byte(0x2BECA25,0x01);
        rom.write_byte(0x2BECA2D,0x01);

    # Fix GS rewards to be static
    rom.write_int32(0xEA3934, 0)
    rom.write_bytes(0xEA3940, [0x10, 0x00])

    # Fix horseback archery rewards to be static
    rom.write_byte(0xE12BA5, 0x00)
    rom.write_byte(0xE12ADD, 0x00)

    # Fix deku theater rewards to be static
    rom.write_bytes(0xEC9A7C, [0x00, 0x00, 0x00, 0x00]) #Sticks
    rom.write_byte(0xEC9CD5, 0x00) #Nuts

    # Fix deku scrub who sells stick upgrade
    rom.write_bytes(0xDF8060, [0x00, 0x00, 0x00, 0x00])

    # Fix deku scrub who sells nut upgrade
    rom.write_bytes(0xDF80D4, [0x00, 0x00, 0x00, 0x00])

    # Fix rolling goron as child reward to be static
    rom.write_bytes(0xED2960, [0x00, 0x00, 0x00, 0x00])

    # Fix proximity text boxes (Navi) (Part 1)
    rom.write_bytes(0xDF8B84, [0x00, 0x00, 0x00, 0x00])

    # Fix final magic bean to cost 99
    rom.write_byte(0xE20A0F, 0x63)
    rom.write_bytes(0x94FCDD, [0x08, 0x39, 0x39])

    # Remove locked door to Boss Key Chest in Fire Temple
    if not world.keysanity and not world.dungeon_mq['Fire Temple']:
        rom.write_byte(0x22D82B7, 0x3F)
    # Remove the unused locked door in water temple
    if not world.dungeon_mq['Water Temple']:
        rom.write_byte(0x25B8197, 0x3F)

    if world.settings.bombchus_in_logic:
        rom.write_int32(rom.sym('BOMBCHUS_IN_LOGIC'), 1)

    # Change graveyard graves to not allow grabbing on to the ledge
    rom.write_byte(0x0202039D, 0x20)
    rom.write_byte(0x0202043C, 0x24)


    # Fix Castle Courtyard to check for meeting Zelda, not Zelda fleeing, to block you
    rom.write_bytes(0xCD5E76, [0x0E, 0xDC])
    rom.write_bytes(0xCD5E12, [0x0E, 0xDC])

    # Cutscene for all medallions never triggers when leaving shadow or spirit temples(hopefully stops warp to colossus on shadow completion with boss reward shuffle)
    rom.write_byte(0xACA409, 0xAD)
    rom.write_byte(0xACA49D, 0xCE)

    # Speed Zelda's Letter scene
    rom.write_bytes(0x290E08E, [0x05, 0xF0])
    rom.write_byte(0xEFCBA7, 0x08)
    rom.write_byte(0xEFE7C7, 0x05)
    #rom.write_byte(0xEFEAF7, 0x08)
    #rom.write_byte(0xEFE7C7, 0x05)
    rom.write_bytes(0xEFE938, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xEFE948, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xEFE950, [0x00, 0x00, 0x00, 0x00])

    # Speed Zelda escaping from Hyrule Castle
    Block_code = [0x00, 0x00, 0x00, 0x01, 0x00, 0x21, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02]
    rom.write_bytes(0x1FC0CF8, Block_code)

    # songs as items flag
    songs_as_items = world.settings.shuffle_song_items or \
                     world.settings.start_with_fast_travel or \
                     world.distribution.song_as_items

    # Speed learning Zelda's Lullaby
    rom.write_int32s(0x02E8E90C, [0x000003E8, 0x00000001]) # Terminator Execution
    if songs_as_items:
        rom.write_int16s(None, [0x0073, 0x001, 0x0002, 0x0002]) # ID, start, end, end
    else:
        rom.write_int16s(None, [0x0073, 0x003B, 0x003C, 0x003C]) # ID, start, end, end


    rom.write_int32s(0x02E8E91C, [0x00000013, 0x0000000C]) # Textbox, Count
    if songs_as_items:
        rom.write_int16s(None, [0xFFFF, 0x0000, 0x0010, 0xFFFF, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2
    else:
        rom.write_int16s(None, [0x0017, 0x0000, 0x0010, 0x0002, 0x088B, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0x00D4, 0x0011, 0x0020, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    # Speed learning Sun's Song
    if songs_as_items:
        rom.write_int32(0x0332A4A4, 0xFFFFFFFF) # Header: frame_count
    else:
        rom.write_int32(0x0332A4A4, 0x0000003C) # Header: frame_count

    rom.write_int32s(0x0332A868, [0x00000013, 0x00000008]) # Textbox, Count
    rom.write_int16s(None, [0x0018, 0x0000, 0x0010, 0x0002, 0x088B, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0x00D3, 0x0011, 0x0020, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    # Speed learning Saria's Song
    if songs_as_items:
        rom.write_int32(0x020B1734, 0xFFFFFFFF) # Header: frame_count
    else:
        rom.write_int32(0x020B1734, 0x0000003C) # Header: frame_count

    rom.write_int32s(0x20B1DA8, [0x00000013, 0x0000000C]) # Textbox, Count
    rom.write_int16s(None, [0x0015, 0x0000, 0x0010, 0x0002, 0x088B, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0x00D1, 0x0011, 0x0020, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    rom.write_int32s(0x020B19C0, [0x0000000A, 0x00000006]) # Link, Count
    rom.write_int16s(0x020B19C8, [0x0011, 0x0000, 0x0010, 0x0000]) #action, start, end, ????
    rom.write_int16s(0x020B19F8, [0x003E, 0x0011, 0x0020, 0x0000]) #action, start, end, ????
    rom.write_int32s(None,         [0x80000000,                          # ???
                                     0x00000000, 0x000001D4, 0xFFFFF731,  # start_XYZ
                                     0x00000000, 0x000001D4, 0xFFFFF712]) # end_XYZ

    # Speed learning Epona's Song
    rom.write_int32s(0x029BEF60, [0x000003E8, 0x00000001]) # Terminator Execution
    if songs_as_items:
        rom.write_int16s(None, [0x005E, 0x0001, 0x0002, 0x0002]) # ID, start, end, end
    else:
        rom.write_int16s(None, [0x005E, 0x000A, 0x000B, 0x000B]) # ID, start, end, end

    rom.write_int32s(0x029BECB0, [0x00000013, 0x00000002]) # Textbox, Count
    if songs_as_items:
        rom.write_int16s(None, [0xFFFF, 0x0000, 0x0009, 0xFFFF, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2
    else:
        rom.write_int16s(None, [0x00D2, 0x0000, 0x0009, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0xFFFF, 0x000A, 0x003C, 0xFFFF, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    # Speed learning Song of Time
    rom.write_int32s(0x0252FB98, [0x000003E8, 0x00000001]) # Terminator Execution
    if songs_as_items:
        rom.write_int16s(None, [0x0035, 0x0001, 0x0002, 0x0002]) # ID, start, end, end
    else:
        rom.write_int16s(None, [0x0035, 0x003B, 0x003C, 0x003C]) # ID, start, end, end

    rom.write_int32s(0x0252FC80, [0x00000013, 0x0000000C]) # Textbox, Count
    if songs_as_items:
        rom.write_int16s(None, [0xFFFF, 0x0000, 0x0010, 0xFFFF, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2
    else:
        rom.write_int16s(None, [0x0019, 0x0000, 0x0010, 0x0002, 0x088B, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0x00D5, 0x0011, 0x0020, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    rom.write_int32(0x01FC3B84, 0xFFFFFFFF) # Other Header?: frame_count

    # Speed learning Song of Storms
    if songs_as_items:
        rom.write_int32(0x03041084, 0xFFFFFFFF) # Header: frame_count
    else:
        rom.write_int32(0x03041084, 0x0000000A) # Header: frame_count

    rom.write_int32s(0x03041088, [0x00000013, 0x00000002]) # Textbox, Count
    rom.write_int16s(None, [0x00D6, 0x0000, 0x0009, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0xFFFF, 0x00BE, 0x00C8, 0xFFFF, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    # Speed learning Minuet of Forest
    if songs_as_items:
        rom.write_int32(0x020AFF84, 0xFFFFFFFF) # Header: frame_count
    else:
        rom.write_int32(0x020AFF84, 0x0000003C) # Header: frame_count

    rom.write_int32s(0x020B0800, [0x00000013, 0x0000000A]) # Textbox, Count
    rom.write_int16s(None, [0x000F, 0x0000, 0x0010, 0x0002, 0x088B, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0x0073, 0x0011, 0x0020, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    rom.write_int32s(0x020AFF88, [0x0000000A, 0x00000005]) # Link, Count
    rom.write_int16s(0x020AFF90, [0x0011, 0x0000, 0x0010, 0x0000]) #action, start, end, ????
    rom.write_int16s(0x020AFFC1, [0x003E, 0x0011, 0x0020, 0x0000]) #action, start, end, ????

    rom.write_int32s(0x020B0488, [0x00000056, 0x00000001]) # Music Change, Count
    rom.write_int16s(None, [0x003F, 0x0021, 0x0022, 0x0000]) #action, start, end, ????

    rom.write_int32s(0x020B04C0, [0x0000007C, 0x00000001]) # Music Fade Out, Count
    rom.write_int16s(None, [0x0004, 0x0000, 0x0000, 0x0000]) #action, start, end, ????

    # Speed learning Bolero of Fire
    if songs_as_items:
        rom.write_int32(0x0224B5D4, 0xFFFFFFFF) # Header: frame_count
    else:
        rom.write_int32(0x0224B5D4, 0x0000003C) # Header: frame_count

    rom.write_int32s(0x0224D7E8, [0x00000013, 0x0000000A]) # Textbox, Count
    rom.write_int16s(None, [0x0010, 0x0000, 0x0010, 0x0002, 0x088B, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0x0074, 0x0011, 0x0020, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    rom.write_int32s(0x0224B5D8, [0x0000000A, 0x0000000B]) # Link, Count
    rom.write_int16s(0x0224B5E0, [0x0011, 0x0000, 0x0010, 0x0000]) #action, start, end, ????
    rom.write_int16s(0x0224B610, [0x003E, 0x0011, 0x0020, 0x0000]) #action, start, end, ????

    rom.write_int32s(0x0224B7F0, [0x0000002F, 0x0000000E]) # Sheik, Count
    rom.write_int16s(0x0224B7F8, [0x0000]) #action
    rom.write_int16s(0x0224B828, [0x0000]) #action
    rom.write_int16s(0x0224B858, [0x0000]) #action
    rom.write_int16s(0x0224B888, [0x0000]) #action

    # Speed learning Serenade of Water
    if songs_as_items:
        rom.write_int32(0x02BEB254, 0xFFFFFFFF) # Header: frame_count
    else:
        rom.write_int32(0x02BEB254, 0x0000003C) # Header: frame_count

    rom.write_int32s(0x02BEC880, [0x00000013, 0x00000010]) # Textbox, Count
    rom.write_int16s(None, [0x0011, 0x0000, 0x0010, 0x0002, 0x088B, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0x0075, 0x0011, 0x0020, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    rom.write_int32s(0x02BEB258, [0x0000000A, 0x0000000F]) # Link, Count
    rom.write_int16s(0x02BEB260, [0x0011, 0x0000, 0x0010, 0x0000]) #action, start, end, ????
    rom.write_int16s(0x02BEB290, [0x003E, 0x0011, 0x0020, 0x0000]) #action, start, end, ????

    rom.write_int32s(0x02BEB530, [0x0000002F, 0x00000006]) # Sheik, Count
    rom.write_int16s(0x02BEB538, [0x0000, 0x0000, 0x018A, 0x0000]) #action, start, end, ????
    rom.write_int32s(None,         [0x1BBB0000,                          # ???
                                     0xFFFFFB10, 0x8000011A, 0x00000330,  # start_XYZ
                                     0xFFFFFB10, 0x8000011A, 0x00000330]) # end_XYZ

    rom.write_int32s(0x02BEC848, [0x00000056, 0x00000001]) # Music Change, Count
    rom.write_int16s(None, [0x0059, 0x0021, 0x0022, 0x0000]) #action, start, end, ????

    # Speed learning Nocturne of Shadow
    rom.write_int32s(0x01FFE458, [0x000003E8, 0x00000001]) # Other Scene? Terminator Execution
    rom.write_int16s(None, [0x002F, 0x0001, 0x0002, 0x0002]) # ID, start, end, end

    rom.write_int32(0x01FFFDF4, 0x0000003C) # Header: frame_count

    rom.write_int32s(0x02000FD8, [0x00000013, 0x0000000E]) # Textbox, Count
    if songs_as_items:
        rom.write_int16s(None, [0xFFFF, 0x0000, 0x0010, 0xFFFF, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2
    else:
        rom.write_int16s(None, [0x0013, 0x0000, 0x0010, 0x0002, 0x088B, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0x0077, 0x0011, 0x0020, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    rom.write_int32s(0x02000128, [0x000003E8, 0x00000001]) # Terminator Execution
    if songs_as_items:
        rom.write_int16s(None, [0x0032, 0x0001, 0x0002, 0x0002]) # ID, start, end, end
    else:
        rom.write_int16s(None, [0x0032, 0x003A, 0x003B, 0x003B]) # ID, start, end, end

    # Speed learning Requiem of Spirit
    rom.write_int32(0x0218AF14, 0x0000003C) # Header: frame_count

    rom.write_int32s(0x0218C574, [0x00000013, 0x00000008]) # Textbox, Count
    if songs_as_items:
        rom.write_int16s(None, [0xFFFF, 0x0000, 0x0010, 0xFFFF, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2
    else:
        rom.write_int16s(None, [0x0012, 0x0000, 0x0010, 0x0002, 0x088B, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0x0076, 0x0011, 0x0020, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    rom.write_int32s(0x0218B478, [0x000003E8, 0x00000001]) # Terminator Execution
    if songs_as_items:
        rom.write_int16s(None, [0x0030, 0x0001, 0x0002, 0x0002]) # ID, start, end, end
    else:
        rom.write_int16s(None, [0x0030, 0x003A, 0x003B, 0x003B]) # ID, start, end, end

    rom.write_int32s(0x0218AF18, [0x0000000A, 0x0000000B]) # Link, Count
    rom.write_int16s(0x0218AF20, [0x0011, 0x0000, 0x0010, 0x0000]) #action, start, end, ????
    rom.write_int32s(None,         [0x40000000,                          # ???
                                     0xFFFFFAF9, 0x00000008, 0x00000001,  # start_XYZ
                                     0xFFFFFAF9, 0x00000008, 0x00000001,  # end_XYZ
                                     0x0F671408, 0x00000000, 0x00000001]) # normal_XYZ
    rom.write_int16s(0x0218AF50, [0x003E, 0x0011, 0x0020, 0x0000]) #action, start, end, ????

    # Speed learning Prelude of Light
    if songs_as_items:
        rom.write_int32(0x0252FD24, 0xFFFFFFFF) # Header: frame_count
    else:
        rom.write_int32(0x0252FD24, 0x0000003C) # Header: frame_count

    rom.write_int32s(0x02531320, [0x00000013, 0x0000000E]) # Textbox, Count
    rom.write_int16s(None, [0x0014, 0x0000, 0x0010, 0x0002, 0x088B, 0xFFFF]) # ID, start, end, type, alt1, alt2
    rom.write_int16s(None, [0x0078, 0x0011, 0x0020, 0x0000, 0xFFFF, 0xFFFF]) # ID, start, end, type, alt1, alt2

    rom.write_int32s(0x0252FF10, [0x0000002F, 0x00000009]) # Sheik, Count
    rom.write_int16s(0x0252FF18, [0x0006, 0x0000, 0x0000, 0x0000]) #action, start, end, ????

    rom.write_int32s(0x025313D0, [0x00000056, 0x00000001]) # Music Change, Count
    rom.write_int16s(None, [0x003B, 0x0021, 0x0022, 0x0000]) #action, start, end, ????

    # Speed scene after Deku Tree
    rom.write_bytes(0x2077E20, [0x00, 0x07, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])
    rom.write_bytes(0x2078A10, [0x00, 0x0E, 0x00, 0x1F, 0x00, 0x20, 0x00, 0x20])
    Block_code = [0x00, 0x80, 0x00, 0x00, 0x00, 0x1E, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF,
                  0xFF, 0xFF, 0x00, 0x1E, 0x00, 0x28, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
    rom.write_bytes(0x2079570, Block_code)

    # Speed scene after Dodongo's Cavern
    rom.write_bytes(0x2221E88, [0x00, 0x0C, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0x2223308, [0x00, 0x81, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])

    # Speed scene after Jabu Jabu's Belly
    rom.write_bytes(0xCA3530, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0x2113340, [0x00, 0x0D, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0x2113C18, [0x00, 0x82, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])
    rom.write_bytes(0x21131D0, [0x00, 0x01, 0x00, 0x00, 0x00, 0x3C, 0x00, 0x3C])

    # Speed scene after Forest Temple
    rom.write_bytes(0xD4ED68, [0x00, 0x45, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0xD4ED78, [0x00, 0x3E, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])
    rom.write_bytes(0x207B9D4, [0xFF, 0xFF, 0xFF, 0xFF])

    # Speed scene after Fire Temple
    rom.write_bytes(0x2001848, [0x00, 0x1E, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])
    rom.write_bytes(0xD100B4, [0x00, 0x62, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0xD10134, [0x00, 0x3C, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])

    # Speed scene after Water Temple
    rom.write_bytes(0xD5A458, [0x00, 0x15, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0xD5A3A8, [0x00, 0x3D, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])
    rom.write_bytes(0x20D0D20, [0x00, 0x29, 0x00, 0xC7, 0x00, 0xC8, 0x00, 0xC8])

    # Speed scene after Shadow Temple
    rom.write_bytes(0xD13EC8, [0x00, 0x61, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0xD13E18, [0x00, 0x41, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])

    # Speed scene after Spirit Temple
    rom.write_bytes(0xD3A0A8, [0x00, 0x60, 0x00, 0x3B, 0x00, 0x3C, 0x00, 0x3C])
    rom.write_bytes(0xD39FF0, [0x00, 0x3F, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00])

    # Speed Nabooru defeat scene
    rom.write_bytes(0x2F5AF84, [0x00, 0x00, 0x00, 0x05])
    rom.write_bytes(0x2F5C7DA, [0x00, 0x01, 0x00, 0x02])
    rom.write_bytes(0x2F5C7A2, [0x00, 0x03, 0x00, 0x04])
    rom.write_byte(0x2F5B369, 0x09)
    rom.write_byte(0x2F5B491, 0x04)
    rom.write_byte(0x2F5B559, 0x04)
    rom.write_byte(0x2F5B621, 0x04)
    rom.write_byte(0x2F5B761, 0x07)

    # Speed scene with all medallions
    rom.write_bytes(0x2512680, [0x00, 0x74, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])

    # Speed collapse of Ganon's Tower
    rom.write_bytes(0x33FB328, [0x00, 0x76, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])

    # Speed Phantom Ganon defeat scene
    rom.write_bytes(0xC944D8, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xC94548, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xC94730, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xC945A8, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xC94594, [0x00, 0x00, 0x00, 0x00])

    # Speed Twinrova defeat scene
    rom.write_bytes(0xD678CC, [0x24, 0x01, 0x03, 0xA2, 0xA6, 0x01, 0x01, 0x42])
    rom.write_bytes(0xD67BA4, [0x10, 0x00])

    # Speed scenes during final battle
    # Ganondorf battle end
    rom.write_byte(0xD82047, 0x09)
    # Zelda descends
    rom.write_byte(0xD82AB3, 0x66)
    rom.write_byte(0xD82FAF, 0x65)
    rom.write_int16s(0xD82D2E, [0x041F])
    rom.write_int16s(0xD83142, [0x006B])
    rom.write_bytes(0xD82DD8, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xD82ED4, [0x00, 0x00, 0x00, 0x00])
    rom.write_byte(0xD82FDF, 0x33)
    # After tower collapse
    rom.write_byte(0xE82E0F, 0x04)
    # Ganon intro
    rom.write_bytes(0xE83D28, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xE83B5C, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xE84C80, [0x10, 0x00])

    # Speed completion of the trials in Ganon's Castle
    rom.write_int16s(0x31A8090, [0x006B, 0x0001, 0x0002, 0x0002]) #Forest
    rom.write_int16s(0x31A9E00, [0x006E, 0x0001, 0x0002, 0x0002]) #Fire
    rom.write_int16s(0x31A8B18, [0x006C, 0x0001, 0x0002, 0x0002]) #Water
    rom.write_int16s(0x31A9430, [0x006D, 0x0001, 0x0002, 0x0002]) #Shadow
    rom.write_int16s(0x31AB200, [0x0070, 0x0001, 0x0002, 0x0002]) #Spirit
    rom.write_int16s(0x31AA830, [0x006F, 0x0001, 0x0002, 0x0002]) #Light

    # Speed obtaining Fairy Ocarina
    rom.write_bytes(0x2151230, [0x00, 0x72, 0x00, 0x3C, 0x00, 0x3D, 0x00, 0x3D])
    Block_code = [0x00, 0x4A, 0x00, 0x00, 0x00, 0x3A, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF,
                  0xFF, 0xFF, 0x00, 0x3C, 0x00, 0x81, 0xFF, 0xFF]
    rom.write_bytes(0x2151240, Block_code)
    rom.write_bytes(0x2150E20, [0xFF, 0xFF, 0xFA, 0x4C])

    if world.shuffle_ocarinas:
        symbol = rom.sym('OCARINAS_SHUFFLED')
        rom.write_byte(symbol,0x01)

    # Speed Zelda Light Arrow cutscene
    rom.write_bytes(0x2531B40, [0x00, 0x28, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])
    rom.write_bytes(0x2532FBC, [0x00, 0x75])
    rom.write_bytes(0x2532FEA, [0x00, 0x75, 0x00, 0x80])
    rom.write_byte(0x2533115, 0x05)
    rom.write_bytes(0x2533141, [0x06, 0x00, 0x06, 0x00, 0x10])
    rom.write_bytes(0x2533171, [0x0F, 0x00, 0x11, 0x00, 0x40])
    rom.write_bytes(0x25331A1, [0x07, 0x00, 0x41, 0x00, 0x65])
    rom.write_bytes(0x2533642, [0x00, 0x50])
    rom.write_byte(0x253389D, 0x74)
    rom.write_bytes(0x25338A4, [0x00, 0x72, 0x00, 0x75, 0x00, 0x79])
    rom.write_bytes(0x25338BC, [0xFF, 0xFF])
    rom.write_bytes(0x25338C2, [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    rom.write_bytes(0x25339C2, [0x00, 0x75, 0x00, 0x76])
    rom.write_bytes(0x2533830, [0x00, 0x31, 0x00, 0x81, 0x00, 0x82, 0x00, 0x82])

    # Speed Bridge of Light cutscene
    rom.write_bytes(0x292D644, [0x00, 0x00, 0x00, 0xA0])
    rom.write_bytes(0x292D680, [0x00, 0x02, 0x00, 0x0A, 0x00, 0x6C, 0x00, 0x00])
    rom.write_bytes(0x292D6E8, [0x00, 0x27])
    rom.write_bytes(0x292D718, [0x00, 0x32])
    rom.write_bytes(0x292D810, [0x00, 0x02, 0x00, 0x3C])
    rom.write_bytes(0x292D924, [0xFF, 0xFF, 0x00, 0x14, 0x00, 0x96, 0xFF, 0xFF])

    #Speed Pushing of All Pushable Objects
    rom.write_bytes(0xDD2B86, [0x40, 0x80])             #block speed
    rom.write_bytes(0xDD2D26, [0x00, 0x01])             #block delay
    rom.write_bytes(0xDD9682, [0x40, 0x80])             #milk crate speed
    rom.write_bytes(0xDD981E, [0x00, 0x01])             #milk crate delay
    rom.write_bytes(0xCE1BD0, [0x40, 0x80, 0x00, 0x00]) #amy puzzle speed
    rom.write_bytes(0xCE0F0E, [0x00, 0x01])             #amy puzzle delay
    rom.write_bytes(0xC77CA8, [0x40, 0x80, 0x00, 0x00]) #fire block speed
    rom.write_bytes(0xC770C2, [0x00, 0x01])             #fire block delay
    rom.write_bytes(0xCC5DBC, [0x29, 0xE1, 0x00, 0x01]) #forest basement puzzle delay
    rom.write_bytes(0xDBCF70, [0x2B, 0x01, 0x00, 0x00]) #spirit cobra mirror startup
    rom.write_bytes(0xDBCF70, [0x2B, 0x01, 0x00, 0x01]) #spirit cobra mirror delay
    rom.write_bytes(0xDBA230, [0x28, 0x41, 0x00, 0x19]) #truth spinner speed
    rom.write_bytes(0xDBA3A4, [0x24, 0x18, 0x00, 0x00]) #truth spinner delay

    #Speed Deku Seed Upgrade Scrub Cutscene
    rom.write_bytes(0xECA900, [0x24, 0x03, 0xC0, 0x00]) #scrub angle
    rom.write_bytes(0xECAE90, [0x27, 0x18, 0xFD, 0x04]) #skip straight to giving item
    rom.write_bytes(0xECB618, [0x25, 0x6B, 0x00, 0xD4]) #skip straight to digging back in
    rom.write_bytes(0xECAE70, [0x00, 0x00, 0x00, 0x00]) #never initialize cs camera
    rom.write_bytes(0xE5972C, [0x24, 0x08, 0x00, 0x01]) #timer set to 1 frame for giving item

    # Remove remaining owls
    rom.write_bytes(0x1FE30CE, [0x01, 0x4B])
    rom.write_bytes(0x1FE30DE, [0x01, 0x4B])
    rom.write_bytes(0x1FE30EE, [0x01, 0x4B])
    rom.write_bytes(0x205909E, [0x00, 0x3F])
    rom.write_byte(0x2059094, 0x80)

    # Darunia won't dance
    rom.write_bytes(0x22769E4, [0xFF, 0xFF, 0xFF, 0xFF])

    # Zora moves quickly
    rom.write_bytes(0xE56924, [0x00, 0x00, 0x00, 0x00])

    # Speed Jabu Jabu swallowing Link
    rom.write_bytes(0xCA0784, [0x00, 0x18, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])

    # Ruto no longer points to Zora Sapphire
    rom.write_bytes(0xD03BAC, [0xFF, 0xFF, 0xFF, 0xFF])

    # Ruto never disappears from Jabu Jabu's Belly
    rom.write_byte(0xD01EA3, 0x00)

    #Shift octorock in jabu forward
    rom.write_bytes(0x275906E, [0xFF, 0xB3, 0xFB, 0x20, 0xF9, 0x56])

    #Move fire/forest temple switches down 1 unit to make it easier to press
    rom.write_bytes(0x24860A8, [0xFC, 0xF4]) #forest basement 1
    rom.write_bytes(0x24860C8, [0xFC, 0xF4]) #forest basement 2
    rom.write_bytes(0x24860E8, [0xFC, 0xF4]) #forest basement 3
    rom.write_bytes(0x236C148, [0x11, 0x93]) #fire hammer room

    # Speed up Epona race start
    rom.write_bytes(0x29BE984, [0x00, 0x00, 0x00, 0x02])
    rom.write_bytes(0x29BE9CA, [0x00, 0x01, 0x00, 0x02])

    # Speed start of Horseback Archery
    #rom.write_bytes(0x21B2064, [0x00, 0x00, 0x00, 0x02])
    #rom.write_bytes(0x21B20AA, [0x00, 0x01, 0x00, 0x02])

    # Speed up Epona escape
    rom.write_bytes(0x1FC8B36, [0x00, 0x2A])

    # Speed up draining the well
    rom.write_bytes(0xE0A010, [0x00, 0x2A, 0x00, 0x01, 0x00, 0x02, 0x00, 0x02])
    rom.write_bytes(0x2001110, [0x00, 0x2B, 0x00, 0xB7, 0x00, 0xB8, 0x00, 0xB8])

    # Speed up opening the royal tomb for both child and adult
    rom.write_bytes(0x2025026, [0x00, 0x01])
    rom.write_bytes(0x2023C86, [0x00, 0x01])
    rom.write_byte(0x2025159, 0x02)
    rom.write_byte(0x2023E19, 0x02)

    #Speed opening of Door of Time
    rom.write_bytes(0xE0A176, [0x00, 0x02])
    rom.write_bytes(0xE0A35A, [0x00, 0x01, 0x00, 0x02])

    # Speed up Lake Hylia Owl Flight
    rom.write_bytes(0x20E60D2, [0x00, 0x01])

    # Speed up Death Mountain Trail Owl Flight
    rom.write_bytes(0x223B6B2, [0x00, 0x01])

    # Poacher's Saw no longer messes up Deku Theater
    rom.write_bytes(0xAE72CC, [0x00, 0x00, 0x00, 0x00])

    # Change Prelude CS to check for medallion
    rom.write_bytes(0x00C805E6, [0x00, 0xA6])
    rom.write_bytes(0x00C805F2, [0x00, 0x01])

    # Change Nocturne CS to check for medallions
    rom.write_bytes(0x00ACCD8E, [0x00, 0xA6])
    rom.write_bytes(0x00ACCD92, [0x00, 0x01])
    rom.write_bytes(0x00ACCD9A, [0x00, 0x02])
    rom.write_bytes(0x00ACCDA2, [0x00, 0x04])

    # Change King Zora to move even if Zora Sapphire is in inventory
    rom.write_bytes(0x00E55BB0, [0x85, 0xCE, 0x8C, 0x3C])
    rom.write_bytes(0x00E55BB4, [0x84, 0x4F, 0x0E, 0xDA])

    # Remove extra Forest Temple medallions
    rom.write_bytes(0x00D4D37C, [0x00, 0x00, 0x00, 0x00])

    # Remove extra Fire Temple medallions
    rom.write_bytes(0x00AC9754, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0x00D0DB8C, [0x00, 0x00, 0x00, 0x00])

    # Remove extra Water Temple medallions
    rom.write_bytes(0x00D57F94, [0x00, 0x00, 0x00, 0x00])

    # Remove extra Spirit Temple medallions
    rom.write_bytes(0x00D370C4, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0x00D379C4, [0x00, 0x00, 0x00, 0x00])

    # Remove extra Shadow Temple medallions
    rom.write_bytes(0x00D116E0, [0x00, 0x00, 0x00, 0x00])

    # Change Mido, Saria, and Kokiri to check for Deku Tree complete flag
    # bitwise pointer for 0x80
    kokiriAddresses = [0xE52836, 0xE53A56, 0xE51D4E, 0xE51F3E, 0xE51D96, 0xE51E1E, 0xE51E7E, 0xE51EDE, 0xE51FC6, 0xE51F96, 0xE293B6, 0xE29B8E, 0xE62EDA, 0xE630D6, 0xE633AA, 0xE6369E]
    for kokiri in kokiriAddresses:
        rom.write_bytes(kokiri, [0x8C, 0x0C])
    # Kokiri
    rom.write_bytes(0xE52838, [0x94, 0x48, 0x0E, 0xD4])
    rom.write_bytes(0xE53A58, [0x94, 0x49, 0x0E, 0xD4])
    rom.write_bytes(0xE51D50, [0x94, 0x58, 0x0E, 0xD4])
    rom.write_bytes(0xE51F40, [0x94, 0x4B, 0x0E, 0xD4])
    rom.write_bytes(0xE51D98, [0x94, 0x4B, 0x0E, 0xD4])
    rom.write_bytes(0xE51E20, [0x94, 0x4A, 0x0E, 0xD4])
    rom.write_bytes(0xE51E80, [0x94, 0x59, 0x0E, 0xD4])
    rom.write_bytes(0xE51EE0, [0x94, 0x4E, 0x0E, 0xD4])
    rom.write_bytes(0xE51FC8, [0x94, 0x49, 0x0E, 0xD4])
    rom.write_bytes(0xE51F98, [0x94, 0x58, 0x0E, 0xD4])
    # Saria
    rom.write_bytes(0xE293B8, [0x94, 0x78, 0x0E, 0xD4])
    rom.write_bytes(0xE29B90, [0x94, 0x68, 0x0E, 0xD4])
    # Mido
    rom.write_bytes(0xE62EDC, [0x94, 0x6F, 0x0E, 0xD4])
    rom.write_bytes(0xE630D8, [0x94, 0x4F, 0x0E, 0xD4])
    rom.write_bytes(0xE633AC, [0x94, 0x68, 0x0E, 0xD4])
    rom.write_bytes(0xE636A0, [0x94, 0x48, 0x0E, 0xD4])

    # Change adult Kokiri Forest to check for Forest Temple complete flag
    rom.write_bytes(0xE5369E, [0xB4, 0xAC])
    rom.write_bytes(0xD5A83C, [0x80, 0x49, 0x0E, 0xDC])

    # Change adult Goron City to check for Fire Temple complete flag
    rom.write_bytes(0xED59DC, [0x80, 0xC9, 0x0E, 0xDC])

    # Change Pokey to check DT complete flag
    rom.write_bytes(0xE5400A, [0x8C, 0x4C])
    rom.write_bytes(0xE5400E, [0xB4, 0xA4])
    if world.open_forest != 'closed':
        rom.write_bytes(0xE5401C, [0x14, 0x0B])

    # Fix Shadow Temple to check for different rewards for scene
    rom.write_bytes(0xCA3F32, [0x00, 0x00, 0x25, 0x4A, 0x00, 0x10])

    # Fix Spirit Temple to check for different rewards for scene
    rom.write_bytes(0xCA3EA2, [0x00, 0x00, 0x25, 0x4A, 0x00, 0x08])

    # Fix Biggoron to check a different flag.
    rom.write_byte(0xED329B, 0x72)
    rom.write_byte(0xED43E7, 0x72)
    rom.write_bytes(0xED3370, [0x3C, 0x0D, 0x80, 0x12])
    rom.write_bytes(0xED3378, [0x91, 0xB8, 0xA6, 0x42, 0xA1, 0xA8, 0xA6, 0x42])
    rom.write_bytes(0xED6574, [0x00, 0x00, 0x00, 0x00])

    # Remove the check on the number of days that passed for claim check.
    rom.write_bytes(0xED4470, [0x00, 0x00, 0x00, 0x00])
    rom.write_bytes(0xED4498, [0x00, 0x00, 0x00, 0x00])

    # Fixed reward order for Bombchu Bowling
    rom.write_bytes(0xE2E698, [0x80, 0xAA, 0xE2, 0x64])
    rom.write_bytes(0xE2E6A0, [0x80, 0xAA, 0xE2, 0x4C])
    rom.write_bytes(0xE2D440, [0x24, 0x19, 0x00, 0x00])

    # Offset kakariko carpenter starting position
    rom.write_bytes(0x1FF93A4, [0x01, 0x8D, 0x00, 0x11, 0x01, 0x6C, 0xFF, 0x92, 0x00, 0x00, 0x01, 0x78, 0xFF, 0x2E, 0x00, 0x00, 0x00, 0x03, 0xFD, 0x2B, 0x00, 0xC8, 0xFF, 0xF9, 0xFD, 0x03, 0x00, 0xC8, 0xFF, 0xA9, 0xFD, 0x5D, 0x00, 0xC8, 0xFE, 0x5F]) # re order the carpenter's path
    rom.write_byte(0x1FF93D0, 0x06) # set the path points to 6
    rom.write_bytes(0x20160B6, [0x01, 0x8D, 0x00, 0x11, 0x01, 0x6C]) # set the carpenter's start position

    # Give hp after first ocarina minigame round
    rom.write_bytes(0xDF2204, [0x24, 0x03, 0x00, 0x02])

    # Allow owl to always carry the kid down Death Mountain
    rom.write_bytes(0xE304F0, [0x24, 0x0E, 0x00, 0x01])

    # Fix Vanilla Dodongo's Cavern Gossip Stone to not use a permanent flag for the fairy
    if not world.dungeon_mq['Dodongos Cavern']:
        rom.write_byte(0x1F281FE, 0x38)

    # Fix "...???" textbox outside Child Colossus Fairy to use the right flag and disappear once the wall is destroyed
    rom.write_byte(0x21A026F, 0xDD)

    # Remove the "...???" textbox outside the Crater Fairy (change it to an actor that does nothing)
    rom.write_int16s(0x225E7DC, [0x00B5, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0xFFFF])

    # Forbid Sun's Song from a bunch of cutscenes
    Suns_scenes = [0x2016FC9, 0x2017219, 0x20173D9, 0x20174C9, 0x2017679, 0x20C1539, 0x20C15D9, 0x21A0719, 0x21A07F9, 0x2E90129, 0x2E901B9, 0x2E90249, 0x225E829, 0x225E939, 0x306D009]
    for address in Suns_scenes:
        rom.write_byte(address,0x01)

    # Allow Warp Songs in additional places
    rom.write_byte(0xB6D3D2, 0x00) # Gerudo Training Grounds
    rom.write_byte(0xB6D42A, 0x00) # Inside Ganon's Castle

    # Allow Farore's Wind in dungeons where it's normally forbidden
    rom.write_byte(0xB6D3D3, 0x00) # Gerudo Training Grounds
    rom.write_byte(0xB6D42B, 0x00) # Inside Ganon's Castle

    # Remove disruptive text from Gerudo Training Grounds and early Shadow Temple (vanilla)
    Wonder_text = [0x27C00BC, 0x27C00CC, 0x27C00DC, 0x27C00EC, 0x27C00FC, 0x27C010C, 0x27C011C, 0x27C012C, 0x27CE080,
                   0x27CE090, 0x2887070, 0x2887080, 0x2887090, 0x2897070, 0x28C7134, 0x28D91BC, 0x28A60F4, 0x28AE084,
                   0x28B9174, 0x28BF168, 0x28BF178, 0x28BF188, 0x28A1144, 0x28A6104, 0x28D0094]
    for address in Wonder_text:
        rom.write_byte(address, 0xFB)

    # Speed dig text for Dampe
    rom.write_bytes(0x9532F8, [0x08, 0x08, 0x08, 0x59])

    # Make item descriptions into a single box
    Short_item_descriptions = [0x92EC84, 0x92F9E3, 0x92F2B4, 0x92F37A, 0x92F513, 0x92F5C6, 0x92E93B, 0x92EA12]
    for address in Short_item_descriptions:
        rom.write_byte(address,0x02)

    et_original = rom.read_bytes(0xB6FBF0, 4 * 0x0614)

    exit_updates = []

    def copy_entrance_record(source_index, destination_index, count=4):
        ti = source_index * 4
        rom.write_bytes(0xB6FBF0 + destination_index * 4, et_original[ti:ti+(4 * count)])

    def generate_exit_lookup_table():
        # Assumes that the last exit on a scene's exit list cannot be 0000
        exit_table = {
            0x0028: [0xAC95C2] #Jabu with the fish is entered from a cutscene hardcode
            }

        def add_scene_exits(scene_start, offset = 0):
            current = scene_start + offset
            exit_list_start_off = 0
            exit_list_end_off = 0
            command = 0

            while command != 0x14:
                command = rom.read_byte(current)
                if command == 0x18: # Alternate header list
                    header_list = scene_start + (rom.read_int32(current + 4) & 0x00FFFFFF)
                    for alt_id in range(0,3):
                        header_offset = rom.read_int32(header_list) & 0x00FFFFFF
                        if header_offset != 0:
                            add_scene_exits(scene_start, header_offset)
                        header_list += 4
                if command == 0x13: # Exit List
                    exit_list_start_off = rom.read_int32(current + 4) & 0x00FFFFFF
                if command == 0x0F: # Lighting list, follows exit list
                    exit_list_end_off = rom.read_int32(current + 4) & 0x00FFFFFF
                current += 8

            if exit_list_start_off == 0 or exit_list_end_off == 0:
                return

            # calculate the exit list length
            list_length = (exit_list_end_off - exit_list_start_off) // 2
            last_id = rom.read_int16(scene_start + exit_list_end_off - 2)
            if last_id == 0:
                list_length -= 1

            # update
            addr = scene_start + exit_list_start_off
            for _ in range(0, list_length):
                index = rom.read_int16(addr)
                if index not in exit_table:
                    exit_table[index] = []
                exit_table[index].append(addr)
                addr += 2

        scene_table = 0x00B71440
        for scene in range(0x00, 0x65):
            scene_start = rom.read_int32(scene_table + (scene * 0x14));
            add_scene_exits(scene_start)

        return exit_table


    def set_entrance_updates(entrances):
        for entrance in entrances:
            new_entrance = entrance.data
            replaced_entrance = entrance.replaces.data

            if entrance.replaces.type == 'Grotto':
                if entrance.replaces.primary:
                    replaced_entrance['index'] = 0x1000 + replaced_entrance['grotto_id']
                else:
                    replaced_entrance['index'] = 0x7FFF

            exit_updates.append((new_entrance['index'], replaced_entrance['index']))

            if "dynamic_address" in new_entrance:
                # Dynamic exits are special and have to be set on a specific address
                rom.write_int16(new_entrance["dynamic_address"], replaced_entrance['index'])

            if "blue_warp" in new_entrance:
                if "blue_warp" in replaced_entrance:
                    blue_out_data =  replaced_entrance["blue_warp"]
                else:
                    blue_out_data = replaced_entrance["index"]
                # Blue warps have multiple hardcodes leading to them. The good news is
                # the blue warps (excluding deku sprout and lake fill special cases) each
                # have a nice consistent 4-entry in the table we can just shuffle. So just
                # catch all the hardcode with entrance table rewrite. This covers the
                # Forest temple and Water temple blue warp revisits. Deku sprout remains
                # vanilla as it never took you to the exit and the lake fill is handled
                # above by removing the cutscene completely. Child has problems with Adult
                # blue warps, so always use the return entrance if a child.
                copy_entrance_record(blue_out_data + 2, new_entrance["blue_warp"] + 2, 2)
                copy_entrance_record(replaced_entrance["index"], new_entrance["blue_warp"], 2)


    exit_table = generate_exit_lookup_table()

    if world.shuffle_interior_entrances or world.shuffle_overworld_entrances:
        # Disable trade quest timers and prevent trade items from ever reverting
        rom.write_byte(rom.sym('DISABLE_TIMERS'), 0x01)
        rom.write_int16s(0xB6D460, [0x0030, 0x0035, 0x0036]) # Change trade items revert table to prevent all reverts

    if world.shuffle_overworld_entrances:
        rom.write_byte(rom.sym('OVERWORLD_SHUFFLED'), 1)

        # Prevent the ocarina cutscene from leading straight to hyrule field
        rom.write_byte(rom.sym('OCARINAS_SHUFFLED'), 1)

        # Disable the fog state entirely to avoid fog glitches
        rom.write_byte(rom.sym('NO_FOG_STATE'), 1)

        # Combine all fence hopping LLR exits to lead to the main LLR exit
        for k in [0x028A, 0x028E, 0x0292]: # Southern, Western, Eastern Gates
            exit_table[0x01F9] += exit_table[k] # Hyrule Field entrance from Lon Lon Ranch (main land entrance)
            del exit_table[k]
        exit_table[0x01F9].append(0xD52722) # 0x0476, Front Gate

        # Combine the water exits between Hyrule Field and Zora River to lead to the land entrance instead of the water entrance
        exit_table[0x00EA] += exit_table[0x01D9] # Hyrule Field -> Zora River
        exit_table[0x0181] += exit_table[0x0311] # Zora River -> Hyrule Field
        del exit_table[0x01D9]
        del exit_table[0x0311]

        # Change Impa escorts to bring link at the hyrule castle grounds entrance from market, instead of hyrule field
        rom.write_int16(0xACAA2E, 0x0138) # 1st Impa escort
        rom.write_int16(0xD12D6E, 0x0138) # 2nd+ Impa escort

        # Change hardcoded Owl Drop entrance indexes to their new indexes (cutscene hardcodes)
        for entrance in world.get_shuffled_entrances(type='OwlDrop'):
            rom.write_int16(entrance.data['code_address'], entrance.replaces.data['index'])

        set_entrance_updates(world.get_shuffled_entrances(type='Overworld'))

    if world.shuffle_dungeon_entrances:
        rom.write_byte(rom.sym('DUNGEONS_SHUFFLED'), 1)

        # Connect lake hylia fill exit to revisit exit (Hylia blue will then be rewired below)
        rom.write_int16(0xAC995A, 0x060C)

        # Remove deku sprout and drop player at SFM after forest (SFM blue will then be rewired by ER below)
        rom.write_int16(0xAC9F96, 0x0608)


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

            # shuffle_messages.shop_item_messages.extend([shop_item.description_message, shop_item.purchase_message])

            if item_display.dungeonitem:
                split_item_name = item_display.name.split('(')
                split_item_name[1] = '(' + split_item_name[1]

                if location.item.name == 'Ice Trap':
                    split_item_name[0] = create_fake_name(split_item_name[0])

                if world.world_count > 1:
                    # description_text = '\x08\x05\x41%s  %d Rupees\x01%s\x01\x05\x42Player %d\x05\x40\x01Special deal! ONE LEFT!\x09\x0A\x02' % (
                    split_item_name[0], location.price, split_item_name[1], location.item.world_id + 1)
                else:
                    # description_text = '\x08\x05\x41%s  %d Rupees\x01%s\x01\x05\x40Special deal! ONE LEFT!\x01Get it while it lasts!\x09\x0A\x02' % (
                    split_item_name[0], location.price, split_item_name[1])
                # purchase_text = '\x08%s  %d Rupees\x09\x01%s\x01\x1B\x05\x42Buy\x01Don\'t buy\x05\x40\x02' % (split_item_name[0], location.price, split_item_name[1])
            else:
                # shop_item_name = getSimpleHintNoPrefix(item_display)
                # if location.item.name == 'Ice Trap':
                #     shop_item_name = create_fake_name(shop_item_name)

                # description_text = '\x08\x05\x41%s  %d Rupees\x01\x05\x40Special deal! ONE LEFT!\x01Get it while it lasts!\x09\x0A\x02' % (item_display, location.price)
                # purchase_text = '\x08%s  %d Rupees\x09\x01\x01\x1B\x05\x42Buy\x01Don\'t buy\x05\x40\x02' % (shop_item_name, location.price)

            # update_message_by_id(messages, shop_item.description_message, description_text, 0x03)
            # update_message_by_id(messages, shop_item.purchase_message, purchase_text, 0x03)

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
