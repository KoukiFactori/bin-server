""" Mapping between python objets and the Redis store """


from redis import Redis
from genpw import pronounceable_passwd
from bin import config


# We always connect to Redis
database = Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB
)


class Snippet:
    """
    A snippet is a immuable text that have been saved in the database
    and that is retrivable via an unique URL.
    """

    def __init__(self, ident, code, views_left, parentid, token=None):
        self.id = ident  #: snippet unique identifier
        self.code = code  #: snippet text
        self.views_left = views_left  #: how many time this snippet can be retrieved again
        self.parentid = parentid  #: the original snippet this one is a duplicate of or an empty string
        self.token = token #: the admin token of the snippet

    @classmethod
    def create(cls, code, maxusage, lifetime, parentid, token=None):
        """
        Save a snippet in the database and return a snippet object

        :param code: the source code utf-8 encoded
        :param maxusage: how many times this snippet can be retrieve before self-deletion
        :param lifetime: how long the snippet is saved before self-deletion
        :param parentid: the original snippet id this new snippet is a duplicate of, empty string for original snippet    
        :param token: the admin token of the snippet
        """
        for _ in range(20):
            ident = pronounceable_passwd(config.IDENTSIZE)
            if not database.exists(ident):
                break
        else:
            raise RuntimeError("No free identifier has been found after 20 attempts")
        database.hset(ident, b'code', code)
        database.hset(ident, b'views_left', maxusage)
        database.hset(ident, b'parentid', parentid)
        if token:
            database.hset(ident, b'token', token)
        if lifetime > 0:
            database.expire(ident, int(lifetime))
        return cls(ident, code, maxusage, parentid)

    @classmethod
    def get_by_id(cls, ident):
        """
        Retrieve a snippet from the database and return a snippet object

        :param ident: the snippet identifier
        :raises KeyError: the snippet does not exist or have been removed
        """
        snippet = database.hgetall(ident)

        if not snippet:
            raise KeyError('Snippet not found')

        code = snippet[b'code'].decode('utf-8')
        views_left = int(snippet[b'views_left'].decode('utf-8'))
        parentid = snippet[b'parentid'].decode('ascii')
        token = None
        if b'token' in snippet:
            token = snippet[b'token'].decode('ascii')
        if views_left == 0:
            pass
        elif views_left == 1:
            database.delete(ident)
        else:
            database.hincrby(ident, 'views_left', -1)

        return cls(ident, code, views_left, parentid, token)

    @classmethod
    def delete_by_id(cls, ident):
        """
        Delete a snippet from the database

        :param ident: the snippet identifier
        :raises KeyError: the snippet does not exist or have been removed
        """
        snippet = database.hgetall(ident)

        if not snippet:
            raise KeyError('Snippet not found')

        database.hdel(ident, *list(snippet.keys()))
