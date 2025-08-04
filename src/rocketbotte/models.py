from enum import Enum


class User:
    def __init__(self, json: dict):
        self.id = json.get("_id")
        self.username = json.get("username")
        self.name = json.get("name")

    @property
    def mention(self) -> str:
        return f"@{self.username}"

    def __str__(self):
        return self.username


class Message:
    def __init__(self, json: dict | list):
        if type(json) is list:
            json = json[0]
        self.json = json

    def __str__(self):
        return f"Message[author : {self.author}, date={self.created_at}, message={self.content}]"

    @property
    def id(self) -> str:
        return self.json.get("_id")

    @property
    def author(self) -> User:
        return User(self.json.get("u"))

    @property
    def room_id(self) -> str:
        return self.json.get("rid")

    @property
    def content(self) -> str:
        return self.json.get("msg")

    @property
    def created_at(self) -> str:
        return self.json.get("ts", {}).get("$date")

    @property
    def edited_at(self) -> str:
        return self.json.get("editedAt", {}).get("$date")

    @property
    def reactions(self) -> str:
        return self.json.get("reaction", {})


subscription_type = {"d": "dm", "c": "channels", "p": "groups"}


class RoomType(Enum):
    C = "c"
    D = "d"
    P = "p"

    @property
    def endpoint(self) -> str:
        return subscription_type.get(self.value)


class Subscription:
    def __init__(self, json: dict):
        self.json = json
        self.user = User(self.json.get("u"))
        self.room_type = RoomType(json.get("t"))

    def __str__(self):
        return f"Subscription[{self.best_name} : {self.room_id}]"

    @property
    def room_id(self) -> str:
        return self.json.get("rid")

    @property
    def name(self) -> str:
        return self.json.get("name")

    @property
    def fname(self) -> str:
        return self.json.get("fname")

    @property
    def best_name(self) -> str:
        return self.fname if self.fname is not None else self.name
