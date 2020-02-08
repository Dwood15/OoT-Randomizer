import collections
import logging
from Location import DisableType
from Search import Search
from State import State


def set_rules(world):
    logger = logging.getLogger('')

    # ganon can only carry triforce
    world.get_location('Ganon').item_rule = lambda location, item: item.name == 'Triforce'

    guarantee_hint = world.parser.parse_rule('guarantee_hint')
    is_child = world.parser.parse_rule('is_child')

    for location in world.get_locations():
        if not world.settings.shuffle_song_items:
            if location.type == 'Song':
                # allow junk items, but songs must still have matching world
                add_item_rule(location, lambda location, item:
                    ((location.world.distribution.song_as_items or world.start_with_fast_travel)
                        and item.type != 'Song')
                    or (item.type == 'Song' and item.world_id == location.world.id))
            else:
                add_item_rule(location, lambda location, item: item.type != 'Song')

        if location.type == 'Shop':
            if location.name in world.shop_prices:
                add_item_rule(location, lambda location, item: item.type != 'Shop')
                location.price = world.shop_prices[location.name]
                location.add_rule(create_shop_rule(location))
            else:
                add_item_rule(location, lambda location, item: item.type == 'Shop' and item.world_id == location.world.id)
        elif 'Deku Scrub' in location.name:
            location.add_rule(create_shop_rule(location))
        else:
            add_item_rule(location, lambda location, item: item.type != 'Shop')

        if location.name == 'Forest Temple MQ First Chest' and world.shuffle_bosskeys == 'dungeon' and world.shuffle_smallkeys == 'dungeon' and world.tokensanity == 'off':
            # This location needs to be a small key. Make sure the boss key isn't placed here.
            forbid_item(location, 'Boss Key (Forest Temple)')

        if location.type == 'GossipStone' and world.hints == 'mask':
            location.add_rule(is_child)

        if location.name in world.always_hints:
            location.add_rule(guarantee_hint)

    for location in world.disabled_locations:
        try:
            world.get_location(location).disabled = DisableType.PENDING
        except:
            logger.debug('Tried to disable location that does not exist: %s' % location)


def create_shop_rule(location):
    def required_wallets(price):
        if price > 500:
            return 3
        if price > 200:
            return 2
        if price > 99:
            return 1
        return 0
    return location.world.parser.parse_rule('(Progressive_Wallet, %d)' % required_wallets(location.price))


def set_rule(spot, rule):
    spot.access_rule = rule


def add_item_rule(spot, rule):
    old_rule = spot.item_rule
    spot.item_rule = lambda location, item: rule(location, item) and old_rule(location, item)


def forbid_item(location, item_name):
    old_rule = location.item_rule
    location.item_rule = lambda loc, item: item.name != item_name and old_rule(loc, item)


def item_in_locations(state, item, locations):
    for location in locations:
        if state.item_name(location) == item:
            return True
    return False


# This function should be run once after the shop items are placed in the world.
# It should be run before other items are placed in the world so that logic has
# the correct checks for them. This is safe to do since every shop is still
# accessible when all items are obtained and every shop item is not.
# This function should also be called when a world is copied if the original world
# had called this function because the world.copy does not copy the rules
def set_shop_rules(world):
    found_bombchus = world.parser.parse_rule('found_bombchus')
    wallet = world.parser.parse_rule('Progressive_Wallet')
    wallet2 = world.parser.parse_rule('(Progressive_Wallet, 2)')
    is_adult = world.parser.parse_rule('is_adult')
    for location in world.get_filled_locations():
        if location.item.type == 'Shop':
            # Add wallet requirements
            if location.item.name in ['Buy Arrows (50)', 'Buy Fish', 'Buy Goron Tunic', 'Buy Bombchu (20)', 'Buy Bombs (30)']:
                location.add_rule(wallet)
            elif location.item.name in ['Buy Zora Tunic', 'Buy Blue Fire']:
                location.add_rule(wallet2)

            # Add adult only checks
            if location.item.name in ['Buy Goron Tunic', 'Buy Zora Tunic']:
                location.add_rule(is_adult)

            # Add item prerequisite checks
            if location.item.name in ['Buy Blue Fire',
                                      'Buy Blue Potion',
                                      'Buy Bottle Bug',
                                      'Buy Fish',
                                      'Buy Green Potion',
                                      'Buy Poe',
                                      'Buy Red Potion [30]',
                                      'Buy Red Potion [40]',
                                      'Buy Red Potion [50]',
                                      'Buy Fairy\'s Spirit']:
                location.add_rule(State.has_bottle)
            if location.item.name in ['Buy Bombchu (10)', 'Buy Bombchu (20)', 'Buy Bombchu (5)']:
                location.add_rule(found_bombchus)


# This function should be ran once after setting up entrances and before placing items
# The goal is to automatically set item rules based on age requirements in case entrances were shuffled
def set_entrances_based_rules(world):
    if isinstance(world, list):
        raise Exception("still passing in a list when we shouldn't !!")

    # Use the states with all items available in the pools for this seed
    complete_itempool = [item for item in world.get_itempool_with_dungeon_items()]
    search = Search([world.state])
    search.collect_all(complete_itempool)
    search.collect_locations()

    for location in world.get_locations():
        if location.type == 'Shop':
            # If All Locations Reachable is on, prevent shops only ever reachable as child from containing Buy Goron Tunic and Buy Zora Tunic items
            if not world.settings.check_beatable_only:
                if not search.can_reach(location.parent_region, age='adult'):
                    forbid_item(location, 'Buy Goron Tunic')
                    forbid_item(location, 'Buy Zora Tunic')
