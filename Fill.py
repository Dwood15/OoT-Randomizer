import logging
import random
from typing import List

from Item import ItemFactory, Item
from ItemList import get_major_items
from ItemPool import remove_junk_items
from Location import DisableType, Location
from Rules import set_shop_rules
from Search import Search
from World import World

logger = logging.getLogger('')


class ShuffleError(RuntimeError):
    pass


class FillError(ShuffleError):
    pass


class PoolHolder:
    def __init__(self, ssitempool: bool):
        self.shuffle_songs_into_itempool: bool = ssitempool
        # item pools
        self.shop_itempool: List[Item] = []
        self.song_itempool: List[Item] = []
        self.base_itempool: List[Item] = []
        self.dungeon_items: List[Item] = []
        self.search = None

        # location pools
        self.song_locations: List[Location] = []
        self.shop_locations: List[Location] = []
        # where all the excess locations are stored. As processing progresses,
        # items are removed from this list.
        self.base_locations: List[Location] = []
        self.state_list = []

    def append_world(self, world):
        self.append_locations(world)
        self.append_worlditems(world)
        # Add the Keysanity'd items to the pool
        self.base_itempool.extend(world.get_unrestricted_dungeon_items())
        self.dungeon_items.extend(world.get_restricted_dungeon_items())

        self.state_list.append(world.state)

    def append_worlditems(self, world: World):
        for item in world.itempool:
            if item.type == 'Shop':
                self.shop_itempool.append(item)
            elif item.type != 'Song' or self.shuffle_songs_into_itempool:
                self.base_itempool.append(item)
            else:
                self.song_itempool.append(item)

    def append_locations(self, world: World):
        # In prior versions, the song location list was populated from a static list of location
        # names. This means that whether or not the location was unfilled didn't matter... It still
        # got added to the song_locations list.
        # I *don't think* any of the song locations were filled when the distribute_items funcs
        # were called, however, it is worth checking.
        # TODO: whether or not a *song* location can be 'filled' when distribute_items_restrictive is called.
        for location in world.get_unfilled_locations():
            if location.type == 'Shop' and location.price is None:
                self.shop_locations.append(location)
            elif location.type != 'Song' or self.shuffle_songs_into_itempool:
                self.song_locations.append(location)
            elif location.type != 'GossipStone':
                self.base_locations.append(location)

    def place_shop_locations(self, window, worlds):
        search = Search(self.state_list)
        fill_ownworld_restrictive(window, worlds, search, self.shop_locations, self.shop_itempool, self.base_itempool + self.song_itempool + self.dungeon_items, "shop")
        search.collect_locations()

    def cloakable_locations(self):
        return self.shop_locations + self.song_locations + self.base_locations

    def location_count(self):
        return len(self.base_locations) + len(self.song_locations) + len(self.shop_locations)

    def models(self):
        return self.shop_itempool + self.dungeon_items + self.song_itempool + self.base_itempool

    def location_pools(self):
        return [self.shop_locations, self.song_locations, self.base_locations]

# Places restricted dungeon items into the worlds. To ensure there is room for them.
# they are placed first so it will assume all other items are reachable
def fill_dungeons_restrictive(window, worlds, search, shuffled_locations, dungeon_items, itempool):
    # List of states with all non-key items
    base_search = search.copy()
    base_search.collect_all(itempool)
    base_search.collect_locations()

    # shuffle this list to avoid placement bias
    random.shuffle(itempool)

    # sort in the order Other, Small Key, Boss Key before placing dungeon items
    # python sort is stable, so the ordering is still random within groups
    # fill_restrictive processes the resulting list backwards so the Boss Keys will actually be placed first
    sort_order = {"BossKey": 3, "SmallKey": 2}

    dungeon_items.sort(key=lambda item: sort_order.get(item.type, 1))

    # place dungeon items
    fill_restrictive(window, worlds, base_search, shuffled_locations, dungeon_items)

# Places all items into the world
def distribute_items_restrictive(window, worlds: List[World]):
    # Generate the itempools, plucking out whether or not to shuffle song items from the first world's settings
    all_pools = PoolHolder(worlds[0].shuffle_song_items)

    for world in worlds:
        all_pools.append_world(world)

    window.locationcount = all_pools.location_count
    window.fillcount = 0

    # randomize item placement order. this ordering greatly affects location-accessibility bias
    random.shuffle(all_pools.base_itempool)

    prog_itm_pool: List[Item] = []
    prio_itm_pool: List[Item] = []
    rem_itm_pool: List[Item] = []

    ice_traps: List[Item] = []

    ice_traps_as_major = worlds[0].settings.ice_trap_appearance == 'major_only'
    ice_traps_as_junk = worlds[0].settings.ice_trap_appearance == 'junk_only'

    junk_items = remove_junk_items.copy()
    junk_items.remove('Ice Trap')

    fake_items: List[Item] = []
    model_items: List[Item] = []
    for item in all_pools.base_itempool:
        # logic-required items
        if item.advancement:
            prog_itm_pool.append(item)
        elif item.priority:
            prio_itm_pool.append(item)
        else:
            rem_itm_pool.append(item)

        # ice trap memes
        if item.name == 'Ice Trap':
            ice_traps.append(item)
            continue
        elif item.majoritem and ice_traps_as_major:
            model_items.append(item)
        elif ice_traps_as_junk and item.name in junk_items:
            model_items.append(item)
        else:  # world[0].settings.ice_trap_appearance == 'anything':
            model_items.append(item)

    # All major/junk items were somehow removed from the pool (can happen in plando)
    if len(model_items) == 0:
        if ice_traps_as_major:
            model_items = ItemFactory(get_major_items())
        elif ice_traps_as_junk: # All junk was removed
            model_items = ItemFactory(junk_items)
        else: # All major items and junk were somehow removed from the pool (can happen in plando)
            model_items = ItemFactory(get_major_items()) + ItemFactory(junk_items)
    while len(ice_traps) > len(fake_items):
        # if there are more ice traps than model items, then double up on model items
        fake_items.extend(model_items)
    for random_item in random.sample(fake_items, len(ice_traps)):
        ice_trap = ice_traps.pop(0)
        ice_trap.looks_like_item = random_item

    itmpools = [all_pools.shop_itempool, all_pools.dungeon_items, all_pools.song_itempool, prog_itm_pool, prio_itm_pool, rem_itm_pool]
    worlds[0].settings.distribution.fill(window, worlds, all_pools.location_pools, itmpools)
    all_pools.base_itempool = prog_itm_pool + prio_itm_pool + rem_itm_pool


    # We place all the shop items first. Like songs, they have a more limited
    # set of locations that they can be placed in, so placing them first will
    # reduce the odds of creating unbeatable seeds. This also avoids needing
    # to create item rules for every location for whether they are a shop item
    # or not. This shouldn't have much affect on item bias.
    if all_pools.shop_locations:
        logger.info('Placing shop items.')
        all_pools.place_shop_locations(window, worlds)
    # Update the shop item access rules
    for world in worlds:
        set_shop_rules(world)


    # If there are dungeon items that are restricted to their original dungeon,
    # we must place them first to make sure that there is always a location to
    # place them. This could probably be replaced for more intelligent item
    # placement, but will leave as is for now
    if all_pools.dungeon_items:
        logger.info('Placing dungeon items.')
        all_pools.search = Search(all_pools.state_list)
        all_pools.fill_dungeons_restrictive(window, worlds, all_pools.search, all_pools.base_locations, all_pools.dungeon_items, all_pools.base_itempool + all_pools.song_itempool)
        all_pools.search.collect_locations()


    # places the songs into the world
    # Currently places songs only at song locations. if there's an option
    # to allow at other locations then they should be in the main pool.
    # Placing songs on their own since they have a relatively high chance
    # of failing compared to other item type. So this way we only have retry
    # the song locations only.
    if not worlds[0].shuffle_song_items:
        logger.info('Placing song items.')
        fill_ownworld_restrictive(window, worlds, all_pools.search, all_pools.song_locations, all_pools.song_itempool, prog_itm_pool, "song")
        all_pools.search.collect_locations()
        all_pools.base_locations += [location for location in all_pools.song_locations if location.item is None]

    # Put one item in every dungeon, needs to be done before other items are
    # placed to ensure there is a spot available for them
    if worlds[0].one_item_per_dungeon:
        logger.info('Placing one major item per dungeon.')
        fill_dungeon_unique_item(window, worlds, all_pools.search, all_pools.base_locations, prog_itm_pool)
        all_pools.search.collect_locations()

    # Place all progression items. This will include keys in keysanity.
    # Items in this group will check for reachability and will be placed
    # such that the game is guaranteed beatable.
    logger.info('Placing progression items.')
    fill_restrictive(window, worlds, all_pools.search, all_pools.base_locations, prog_itm_pool)
    all_pools.search.collect_locations()

    # Place all priority items.
    # These items are items that only check if the item is allowed to be
    # placed in the location, not checking reachability. This is important
    # for things like Ice Traps that can't be found at some locations
    logger.info('Placing priority items.')
    fill_restrictive_fast(window, worlds, all_pools.base_locations, prio_itm_pool)

    # Place the rest of the items.
    # No restrictions at all. Places them completely randomly. Since they
    # cannot affect the beatability, we don't need to check them
    logger.info('Placing the rest of the items.')
    fast_fill(window, all_pools.base_locations, rem_itm_pool)

    # Log unplaced item/location warnings
    for item in prog_itm_pool + prio_itm_pool + rem_itm_pool:
        logger.error('Unplaced Items: %s [World %d]' % (item.name, item.world.id))
    for location in all_pools.base_locations:
        logger.error('Unfilled Locations: %s [World %d]' % (location.name, location.world.id))

    if prog_itm_pool + prio_itm_pool + rem_itm_pool:
        raise FillError('Not all items are placed.')

    if all_pools.base_locations:
        raise FillError('Not all locations have an item.')

    if not all_pools.search.can_beat_game():
        raise FillError('Cannot beat game!')

    worlds[0].settings.distribution.cloak(worlds, [all_pools.cloakable_locations()], [all_pools.models])

    for world in worlds:
        for location in world.get_filled_locations():
            # Get the maximum amount of wallets required to purchase an advancement item.
            if world.maximum_wallets < 3 and location.price and location.item.advancement:
                if location.price > 500:
                    world.maximum_wallets = 3
                elif world.maximum_wallets < 2 and location.price > 200:
                    world.maximum_wallets = 2
                elif world.maximum_wallets < 1 and location.price > 99:
                    world.maximum_wallets = 1

            # Get Light Arrow location for later usage.
            if location.item and location.item.name == 'Light Arrows':
                location.item.world.light_arrow_location = location


# Places items into dungeon locations. This is used when there should be exactly
# one progression item per dungeon. This should be ran before all the progression
# items are places to ensure there is space to place them.
def fill_dungeon_unique_item(window, worlds, search, fill_locations, base_itempool):
    # We should make sure that we don't count event items, shop items,
    # token items, or dungeon items as a major item. base_itempool at this
    # point should only be able to have tokens of those restrictions
    # since the rest are already placed.
    major_items = [item for item in base_itempool if item.majoritem]
    minor_items = [item for item in base_itempool if not item.majoritem]

    dungeons = [dungeon for world in worlds for dungeon in world.dungeons]
    double_dungeons = []
    for dungeon in dungeons:
        # we will count spirit temple twice so that it gets 2 items to match vanilla
        if dungeon.name == 'Spirit Temple':
            double_dungeons.append(dungeon)
    dungeons.extend(double_dungeons)

    random.shuffle(dungeons)
    random.shuffle(base_itempool)

    base_search = search.copy()
    base_search.collect_all(minor_items)
    base_search.collect_locations()
    all_dungeon_locations = []

    # iterate of all the dungeons in a random order, placing the item there
    for dungeon in dungeons:
        dungeon_locations = [location for region in dungeon.regions for location in region.locations if location in fill_locations]

        # cache this list to flag afterwards
        all_dungeon_locations.extend(dungeon_locations)

        # place 1 item into the dungeon
        fill_restrictive(window, worlds, base_search, dungeon_locations, major_items, 1)

        # update the location and item pool, removing any placed items and filled locations
        # the fact that you can remove items from a list you're iterating over is python magic
        for item in base_itempool:
            if item.location != None:
                fill_locations.remove(item.location)
                base_itempool.remove(item)

    # flag locations to not place further major items. it's important we do it on the
    # locations instead of the dungeon because some locations are not in the dungeon
    for location in all_dungeon_locations:
        location.minor_only = True

    logger.info("Unique dungeon items placed")


# Places items restricting placement to the recipient player's own world
def fill_ownworld_restrictive(window, worlds, search, locations, ownpool, base_itempool, description="Unknown", attempts=15):
    # get the locations for each world

    # look for preplaced items
    placed_prizes = [loc.item.name for loc in locations if loc.item is not None]
    unplaced_prizes = [item for item in ownpool if item.name not in placed_prizes]
    empty_locations = [loc for loc in locations if loc.item is None]

    prizepool_dict = {world.id: [item for item in unplaced_prizes if item.world.id == world.id] for world in worlds}
    prize_locs_dict = {world.id: [loc for loc in empty_locations if loc.world.id == world.id] for world in worlds}

    # Shop item being sent in to this method are tied to their own world.
    # Therefore, let's do this one world at a time. We do this to help
    # increase the chances of successfully placing songs
    for world in worlds:
        # List of states with all items
        unplaced_prizes = [item for item in unplaced_prizes if item not in prizepool_dict[world.id]]
        base_search = search.copy()
        base_search.collect_all(base_itempool + unplaced_prizes)

        world_attempts = attempts
        while world_attempts:
            world_attempts -= 1
            try:
                prizepool = list(prizepool_dict[world.id])
                prize_locs = list(prize_locs_dict[world.id])
                random.shuffle(prizepool)
                fill_restrictive(window, worlds, base_search, prize_locs, prizepool)

                logger.info("Placed %s items for world %s.", description, (world.id + 1))
            except FillError as e:
                logger.info("Failed to place %s items for world %s. Will retry %s more times.", description, (world.id + 1), world_attempts)
                for location in prize_locs_dict[world.id]:
                    location.item = None
                    if location.disabled == DisableType.DISABLED:
                        location.disabled = DisableType.PENDING
                logger.info('\t%s' % str(e))
                continue
            break
        else:
            raise FillError('Unable to place %s items in world %d' % (description, (world.id + 1)))


# Places items in the base_itempool into locations.
# worlds is a list of worlds and is redundant of the worlds in the base_state_list
# base_state_list is a list of world states prior to placing items in the item pool
# items and locations have pointers to the world that they belong to
#
# The algorithm places items in the world in reverse.
# This means we first assume we have every item in the item pool and
# remove an item and try to place it somewhere that is still reachable
# This method helps distribution of items locked behind many requirements
#
# count is the number of items to place. If count is negative, then it will place
# every item. Raises an error if specified count of items are not placed.
#
# This function will modify the location and base_itempool arguments. placed items and
# filled locations will be removed. If this returns and error, then the state of
# those two lists cannot be guaranteed.
def fill_restrictive(window, worlds, base_search, locations, base_itempool, count=-1):
    unplaced_items = []

    # don't run over this search, just keep it as an item collection
    items_search = base_search.copy()
    items_search.collect_all(base_itempool)

    # loop until there are no items or locations
    while base_itempool and locations:
        # if remaining count is 0, return. Negative means unbounded.
        if count == 0:
            break

        # get an item and remove it from the base_itempool
        item_to_place = base_itempool.pop()
        if item_to_place.majoritem:
            l2cations = [l for l in locations if not l.minor_only]
        else:
            l2cations = locations
        random.shuffle(l2cations)

        # generate the max search with every remaining item
        # this will allow us to place this item in a reachable location
        items_search.uncollect(item_to_place)
        max_search = items_search.copy()
        max_search.collect_locations()

        # perform_access_check checks location reachability
        perform_access_check = True
        if worlds[0].check_beatable_only:
            # if any world can not longer be beatable with the remaining items
            # then we must check for reachability no matter what.
            # This way the reachability test is monotonic. If we were to later
            # stop checking, then we could place an item needed in one world
            # in an unreachable place in another world.
            # scan_for_items would cause an unnecessary copy+collect
            perform_access_check = not max_search.can_beat_game(scan_for_items=False)

        # find a location that the item can be placed. It must be a valid location
        # in the world we are placing it (possibly checking for reachability)
        spot_to_fill = None
        for location in l2cations:
            if location.can_fill(max_search.state_list[location.world.id], item_to_place, perform_access_check):
                # for multiworld, make it so that the location is also reachable
                # in the world the item is for. This is to prevent early restrictions
                # in one world being placed late in another world. If this is not
                # done then one player may be waiting a long time for other players.
                if location.world.id != item_to_place.world.id:
                    try:
                        source_location = item_to_place.world.get_location(location.name)
                        if not source_location.can_fill(max_search.state_list[item_to_place.world.id], item_to_place, perform_access_check):
                            # location wasn't reachable in item's world, so skip it
                            continue
                    except KeyError:
                        # This location doesn't exist in the other world, let's look elsewhere.
                        # Check access to whatever parent region exists in the other world.
                        can_reach = True
                        parent_region = location.parent_region
                        while parent_region:
                            try:
                                source_region = item_to_place.world.get_region(parent_region.name)
                                can_reach = max_search.can_reach(source_region)
                                break
                            except KeyError:
                                parent_region = parent_region.entrances[0].parent_region
                        if not can_reach:
                            continue

                if location.disabled == DisableType.PENDING:
                    if not max_search.can_beat_game(False):
                        continue
                    location.disabled = DisableType.DISABLED

                # location is reachable (and reachable in item's world), so place item here
                spot_to_fill = location
                break

        # if we failed to find a suitable location
        if spot_to_fill is None:
            # if we specify a count, then we only want to place a subset, so a miss might be ok
            if count > 0:
                # don't decrement count, we didn't place anything
                unplaced_items.append(item_to_place)
                items_search.collect(item_to_place)
                continue
            else:
                # we expect all items to be placed
                raise FillError('Game unbeatable: No more spots to place %s [World %d] from %d locations (%d total); %d other items left to place, plus %d skipped' % (
                    item_to_place, item_to_place.world.id + 1, len(l2cations), len(locations), len(base_itempool), len(unplaced_items)))

        # Place the item in the world and continue
        spot_to_fill.world.push_item(spot_to_fill, item_to_place)
        locations.remove(spot_to_fill)
        window.fillcount += 1
        window.update_progress(5 + ((window.fillcount / window.locationcount) * 30))

        # decrement count
        count -= 1

    # assert that the specified number of items were placed
    if count > 0:
        raise FillError('Could not place the specified number of item. %d remaining to be placed.' % count)
    if count < 0 and len(base_itempool) > 0:
        raise FillError('Could not place all the items. %d remaining to be placed.' % len(base_itempool))
    # re-add unplaced items that were skipped
    base_itempool.extend(unplaced_items)


# This places items in the base_itempool into the locations
# It does not check for reachability, only that the item is
# allowed in the location
def fill_restrictive_fast(window, worlds, locations, base_itempool):
    while base_itempool and locations:
        item_to_place = base_itempool.pop()
        random.shuffle(locations)

        # get location that allows this item
        spot_to_fill = None
        for location in locations:
            if location.can_fill_fast(item_to_place):
                spot_to_fill = location
                break

        # if we failed to find a suitable location, then stop placing items
        # we don't need to check beatability since world must be beatable
        # at this point
        if spot_to_fill is None:
            if not worlds[0].check_beatable_only:
                logger.debug('Not all items placed. Game beatable anyway.')
            break

        # Place the item in the world and continue
        spot_to_fill.world.push_item(spot_to_fill, item_to_place)
        locations.remove(spot_to_fill)
        window.fillcount += 1
        window.update_progress(5 + ((window.fillcount / window.locationcount) * 30))


# this places item in item_pool completely randomly into
# fill_locations. There is no checks for validity since
# there should be none for these remaining items
def fast_fill(window, locations, base_itempool):
    random.shuffle(locations)
    while base_itempool and locations:
        spot_to_fill = locations.pop()
        item_to_place = base_itempool.pop()
        spot_to_fill.world.push_item(spot_to_fill, item_to_place)
        window.fillcount += 1
        window.update_progress(5 + ((window.fillcount / window.locationcount) * 30))
