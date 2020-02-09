from Location import Location
from Region import Region


class Entrance(object):

    def __init__(self, name='', parent=None):
        self.name = name
        self.parent_region = parent
        self.connected_region = None
        self.access_rule = lambda state, **kwargs: True
        self.access_rules = []
        self.reverse = None
        self.replaces = None
        self.assumed = None
        self.type = None
        self.shuffled = False
        self.data = None
        self.primary = False

    def copy(self, new_region):
        new_entrance = Entrance(self.name, new_region)
        new_entrance.connected_region = self.connected_region.name
        new_entrance.access_rule = self.access_rule
        new_entrance.access_rules = list(self.access_rules)
        new_entrance.reverse = self.reverse
        new_entrance.replaces = self.replaces
        new_entrance.assumed = self.assumed
        new_entrance.type = self.type
        new_entrance.shuffled = self.shuffled
        new_entrance.data = self.data
        new_entrance.primary = self.primary

        return new_entrance

    @property
    def world(self):
        raise Exception("ENTRANCE world SHOULD NOT be referenced")

    def add_rule(self, lambda_rule):
        self.access_rules.append(lambda_rule)
        self.access_rule = lambda state, **kwargs: all(rule(state, **kwargs) for rule in self.access_rules)

    def set_rule(self, lambda_rule):
        self.access_rule = lambda_rule
        self.access_rules = [lambda_rule]

    def connect(self, region):
        self.connected_region = region
        region.entrances.append(self)

    def disconnect(self):
        self.connected_region.entrances.remove(self)
        previously_connected = self.connected_region
        self.connected_region = None
        return previously_connected

    def assume_reachable(self, root_exit=None):
        if root_exit is None:
            raise Exception("root_exit must not be none")

        if not isinstance(root_exit, Entrance) and not isinstance(root_exit, Location) and not isinstance(root_exit, Region):
            raise Exception("root_exit must not be instance of a WORLD")

        if not self.assumed:
            target_region = self.disconnect()
            assumed_entrance = Entrance('Root -> ' + target_region.name, root_exit)
            assumed_entrance.connect(target_region)
            root_exit.exits.append(assumed_entrance)
            assumed_entrance.replaces = self
            self.assumed = assumed_entrance
        return self.assumed

    def bind_two_way(self, other_entrance):
        self.reverse = other_entrance
        other_entrance.reverse = self

    def __str__(self):
        return str(self.__unicode__())

    def __unicode__(self):
        return '%s' % self.name
