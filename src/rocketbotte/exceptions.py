class NoPingException(Exception):
    def __init__(self, seconds):
        super().__init__(f"No ping from server since {seconds} seconds")
