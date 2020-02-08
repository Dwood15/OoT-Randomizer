from ItemList import item_table


class ItemInfo(object):
    items = {}
    events = {}
    bottles = set()

    def __init__(self, name='', event=False):
        if event:
            type = 'Event'
            progressive = True
            itemID = None
            special = None
        else:
            (type, progressive, itemID, special) = item_table[name]

        self.name = name
        self.advancement = (progressive == True)
        self.priority = (progressive == False)
        self.type = type
        self.special = special or {}
        self.index = itemID
        self.price = self.special.get('price')
        self.bottle = self.special.get('bottle', False)

    @staticmethod
    def isBottle(name):
        return name in ItemInfo.bottles


for item_name in item_table:
    ItemInfo.items[item_name] = ItemInfo(item_name)
    if ItemInfo.items[item_name].bottle:
        ItemInfo.bottles.add(item_name)


class Item(object):

    def __init__(self, name='', world=None, event=False):
        if world is None:
            raise Exception("sussing out initialization to empty world ")

        self.name = name
        self.location = None
        self.event = event
        if event:
            if name not in ItemInfo.events:
                ItemInfo.events[name] = ItemInfo(name, event=True)
            self.info = ItemInfo.events[name]
        else:
            self.info = ItemInfo.items[name]
        self.price = self.info.special.get('price')
        self.__world = world
        self.looks_like_item = None
        self.advancement = self.info.advancement
        self.priority = self.info.priority
        self.type = self.info.type
        self.special = self.info.special
        self.index = self.info.index


    item_worlds_to_fix = {}

    def copy(self, new_world=None):
        if new_world is not None and self.__world is not None and new_world.id != self.__world.id:
            raise Exception("Making a copy with a new world that does not match the original world")

        new_item = Item(self.name, new_world, self.event)
        new_item.price = self.price

        if new_world is None and self.__world is not None:
            Item.item_worlds_to_fix[new_item] = self.__world.id

        return new_item

    @property
    def world(self):
        raise Exception("Trying to suss out more fucking circular references holy fucking shit")

    @classmethod
    def fix_worlds_after_copy(cls, worlds):
        items_fixed = []
        for item, world_id in cls.item_worlds_to_fix.items():
            item.__world = worlds[world_id]
            items_fixed.append(item)
        for item in items_fixed:
            del cls.item_worlds_to_fix[item]

    @property
    def world_id(self):
        if self.__world is None:
            raise Exception("__world for item: [%s] is None! What happened?!?", self.name)

        return self.__world.id

    @property
    def key(self):
        return self.smallkey or self.bosskey

    @property
    def genericName(self):
        if self.dungeonitem:
            return self.type
        else:
            return self.name

    @property
    def smallkey(self):
        return self.type == 'SmallKey' or self.type == 'FortressSmallKey'


    @property
    def bosskey(self):
        return self.type == 'BossKey'


    @property
    def map(self):
        return self.type == 'Map'


    @property
    def compass(self):
        return self.type == 'Compass'


    @property
    def dungeonitem(self):
        return self.smallkey or self.bosskey or self.map or self.compass


    @property
    def majoritem(self):
        if self.type == 'Token':
            return self.__world.bridge == 'tokens'

        if self.type in ('Drop', 'Event', 'Shop', 'DungeonReward') or not self.advancement:
            return False

        if self.name.startswith('Bombchus') and not self.__world.bombchus_in_logic:
            return False

        if self.map or self.compass:
            return False
        if self.smallkey and self.__world.shuffle_smallkeys in ['dungeon', 'vanilla']:
            return False
        if self.bosskey and not self.name.endswith('(Ganons Castle)') and self.__world.shuffle_bosskeys in ['dungeon', 'vanilla']:
            return False
        if self.bosskey and self.name.endswith('(Ganons Castle)') and self.__world.shuffle_ganon_bosskey in ['dungeon', 'vanilla']:
            return False

        return True


    def __str__(self):
        return str(self.__unicode__())


    def __unicode__(self):
        return '%s' % self.name


def ItemFactory(items, world=None, event=False):
    if world is None:
        raise Exception("world should never be none, but it is anyway. RIP")

    if isinstance(items, str):
        if not event and items not in ItemInfo.items:
            raise KeyError('Unknown Item: %s', items)
        return Item(items, world, event)

    ret = []
    for item in items:
        if not event and item not in ItemInfo.items:
            raise KeyError('Unknown Item: %s', item)
        ret.append(Item(item, world, event))

    return ret


def MakeEventItem(name, location):
    item = ItemFactory(name, location.world, event=True)
    location.world.push_item(location, item)
    location.locked = True
    if name not in item_table:
        location.internal = True
    location.world.settings.event_items.add(name)
    return item


def IsItem(name):
    return name in item_table


def ItemIterator(predicate=lambda loc: True, world=None):
    if world is None:
        raise Exception("world should never be none, but it is anyway. RIP")

    for item_name in item_table:
        item = ItemFactory(item_name, world)
        if predicate(item):
            yield item
