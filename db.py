import pymongo
from analyze import Status

class Db(object):
    def __init__(self):
        self.client = pymongo.MongoClient()
        self.table = self.client.rain.rain
        
    def _idkey(self, key):
        return {"_id": key}
    
    def _getValue(self, key):
        result = self.table.find_one(self._idkey(key))
        if result:
            result = result[key]
        return result
    
    def _setValue(self, key, value):
        self.table.find_one_and_replace(self._idkey(key), {key: value}, upsert=True)
    
    def getStatus(self):
        status = self._getValue("status")
        if not status:
            return {}
        for key in status:
            status[key] = Status(status[key]["start"], status[key]["end"], status[key]["type"])
        return status
    
    def setStatus(self, status):
        for key in status:
            status[key] = {"start": status[key].start, "end": status[key].end, "type": status[key].type}
        self._setValue("status", status)
            
    def getHash(self):
        return self._getValue("hash")
    
    def setHash(self, h):
        self._setValue("hash", h)
    
    def getUsers(self):
        users = self._getValue("users")
        if users is None:
            self.table.insert(self._idkey("users"), {'users': []})
            return []
        return users
    
    def addUser(self, user):
        self.getUsers()
        self.table.find_one_and_update(self._idkey("users"), {"$addToSet": {'users': user}})
        
    def removeUser(self, user):
        self.getUsers()
        self.table.find_one_and_update(self._idkey("users"), {"$pull": {'users': user}})
        
        


