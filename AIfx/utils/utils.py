import omitempty


def str_bool(text):
    if text.lower() == 'true':
        return True
    else:
        return False


class Serializer(object):
    @property
    def value(self):
        dict_values = omitempty(self.__dict__)
        if not dict_values:
            return None
        return self.__dict__