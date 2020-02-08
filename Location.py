from LocationList import location_table
from Region import TimeOfDay
from enum import Enum


class Location(object):

    def __init__(self, name='', address=None, address2=None, default=None, type='Chest', scene=None, parent=None, filter_tags=None, internal=False, world=None, ui=False, world_id=None):
        self.name = name
        self.parent_region = parent
        self.item = None
        self.address = address
        self.address2 = address2
        self.default = default
        self.type = type
        self.scene = scene
        self.internal = internal
        self.staleness_count = 0
        self.access_rule = lambda state, **kwargs: True
        self.access_rules = []
        self.item_rule = lambda location, item: True
        self.locked = False
        self.price = None
        self.minor_only = False
        self.disabled = DisableType.ENABLED
        if filter_tags is None:
            self.filter_tags = None
        else:
            self.filter_tags = list(filter_tags)

        if not ui:
            if world is None and world_id is None:
                raise Exception("non-ui usage of Location has no world!")
            elif world_id is not None:
                self.world_id = world_id
            else:
                self.world_id = world.id

    def copy(self, new_region):
        new_location = Location(self.name, self.address, self.address2, self.default, self.type, self.scene, new_region, self.filter_tags, world_id=self.world_id)
        if self.item:
            new_location.item = self.item.copy(new_region.world)
            new_location.item.location = new_location
        new_location.access_rule = self.access_rule
        new_location.access_rules = list(self.access_rules)
        new_location.item_rule = self.item_rule
        new_location.locked = self.locked
        new_location.internal = self.internal
        new_location.minor_only = self.minor_only
        new_location.disabled = self.disabled

        return new_location

    @property
    def world(self):
        raise Exception("LOCATION WORLDSTARRRRR")

    def add_rule(self, lambda_rule):
        self.access_rules.append(lambda_rule)
        self.access_rule = lambda state, **kwargs: all(rule(state, **kwargs) for rule in self.access_rules)

    def set_rule(self, lambda_rule):
        self.access_rule = lambda_rule
        self.access_rules = [lambda_rule]

    def can_fill(self, state, item, check_access=True, settings=None):
        if settings is None:
            raise Exception("can fill settings unset entirely")

        if self.minor_only and item.is_majoritem(settings):
            return False

        return (
            not self.is_disabled() and
            self.can_fill_fast(item) and
            (not check_access or state.search.spot_access(self, 'either')))


    def can_fill_fast(self, item, manual=False, settings=None):
        if settings is None:
            raise Exception("can fill settings unset entirely")

        return (self.parent_region.can_fill(item=item, manual=manual, settings=settings) and self.item_rule(self, item))


    def is_disabled(self):
        return (self.disabled == DisableType.DISABLED) or \
               (self.disabled == DisableType.PENDING and self.locked)


    # Can the player see what's placed at this location without collecting it?
    # Used to reduce JSON spoiler noise

    def has_preview(self, settings):
        if self.type in ('Collectable', 'BossHeart', 'GS Token', 'Shop'):
            return True
        if self.type == 'Chest':
            return self.scene == 0x10 or settings.correct_chest_sizes  # Treasure Chest Game Prize or CSMC
        if self.type == 'NPC':
            return self.scene in (0x4B, 0x51, 0x57) # Bombchu Bowling, Hyrule Field (OoT), Lake Hylia (RL/FA)
        return False

    def has_item(self):
        return self.item is not None

    def has_no_item(self):
        return self.item is None

    def has_progression_item(self):
        return self.item is not None and self.item.advancement


    def __str__(self):
        return str(self.__unicode__())


    def __unicode__(self):
        return '%s' % self.name


def LocationFactory(locations, world=None):
    if world is None:
        raise Exception("Location WORLD is NONE")

    ret = []
    singleton = False
    if isinstance(locations, str):
        locations = [locations]
        singleton = True
    for location in locations:
        if location in location_table:
            type, scene, default, addresses, filter_tags = location_table[location]
            if addresses is None:
                addresses = (None, None)
            address, address2 = addresses
            ret.append(Location(location, address, address2, default, type, scene, filter_tags=filter_tags, world=world))
        else:
            raise KeyError('Unknown Location: %s', location)

    if singleton:
        return ret[0]
    return ret


def LocationIterator(predicate=lambda loc: True):
    for location_name in location_table:
        location = LocationFactory(location_name)
        if predicate(location):
            yield location


def UILocationFactory(locations):
    ret = []
    singleton = False
    if isinstance(locations, str):
        locations = [locations]
        singleton = True
    for location in locations:
        if location in location_table:
            type, scene, default, addresses, filter_tags = location_table[location]
            if addresses is None:
                addresses = (None, None)
            address, address2 = addresses
            ret.append(Location(location, address, address2, default, type, scene, filter_tags=filter_tags, ui=True))
        else:
            raise KeyError('Unknown Location: %s', location)

    if singleton:
        return ret[0]
    return ret


def UILocationIterator(predicate=lambda loc: True):
    for location_name in location_table:
        location = UILocationFactory(location_name)
        if predicate(location):
            yield location

def IsLocation(name):
    return name in location_table


class DisableType(Enum):
    ENABLED  = 0
    PENDING = 1
    DISABLED = 2

