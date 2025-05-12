from enum import Enum


class User():  
    def __init__(self, json:dict):
        self.id = json.get('_id')
        self.username = json.get('username')
        self.name = json.get('name')

class Message():    
    def __init__(self, json:dict):
        self.json = json
        
    @property
    def author(self) -> User:
        return User(self.json.get('u'))
    
    @property
    def roomId(self) -> str:
        return self.json.get('rit')
    
    @property
    def content(self) -> str:
        return self.json.get('msg')
    
    @property
    def created_at(self) -> str:
        return self.json.get('ts')

subscription_type = {'d' : 'dm', 'c' : 'channels', 'p': 'groups'}
class RoomType(Enum):

    C = 'c'
    D = 'd'
    P = 'p'
    
    @property
    def endpoint(self) -> str:
        return subscription_type.get(self.value)
    
class Subscriptions:
    def __init__(self, json:dict):
        self.json = json
        self.user = User(self.json.get('u'))
        self.room_type = RoomType(json.get('t'))
    
    @property
    def room_id(self) -> str:
        return self.json.get('rid')       
    
    @property
    def name(self) -> str:
        return self.json.get('name')
    
    @property
    def fname(self) -> str:
        return self.json.get('fname')
    
    @property
    def best_name(self) -> str:
        return self.fname if self.fname is not None else self.name
    
    
    


