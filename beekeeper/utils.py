

class processed:
    """A wrapper around file reading that strips newlines and UTF decodes output"""
    def __init__(self, f):
        self.f = f

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            line = self.f.readline().decode('utf-8')
            if line.strip():
                return line
            elif not line:
                raise StopIteration()

    def read(self):
        return self.f.read().decode('utf-8')
