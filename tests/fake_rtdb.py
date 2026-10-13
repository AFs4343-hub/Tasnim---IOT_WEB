"""Tiny in-memory stand-in for firebase_admin.db (offline tests only)."""
import copy


class FakeRtdb:
    def __init__(self, data=None):
        self.data = copy.deepcopy(data) if data else {}
        self.writes = []

    def reference(self, path):
        return FakeRef(self, [p for p in path.strip("/").split("/") if p])

    def get_path(self, parts):
        node = self.data
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return copy.deepcopy(node)

    def set_path(self, parts, value):
        self.writes.append(("/".join(parts), copy.deepcopy(value)))
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        if value is None:
            node.pop(parts[-1], None)
        else:
            node[parts[-1]] = copy.deepcopy(value)


class FakeRef:
    def __init__(self, db, parts, start=None, end=None):
        self.db, self.parts, self.start, self.end = db, parts, start, end

    def get(self):
        value = self.db.get_path(self.parts)
        if isinstance(value, dict) and (self.start is not None or self.end is not None):
            value = {k: v for k, v in value.items()
                     if (self.start is None or k >= self.start)
                     and (self.end is None or k <= self.end)} or None
        return value

    def order_by_key(self):
        return self

    def start_at(self, key):
        return FakeRef(self.db, self.parts, key, self.end)

    def end_at(self, key):
        return FakeRef(self.db, self.parts, self.start, key)

    def transaction(self, fn):
        new = fn(self.db.get_path(self.parts))
        self.db.set_path(self.parts, new)
        return copy.deepcopy(new)

    def update(self, values):
        for key, value in values.items():
            self.db.set_path(self.parts + key.split("/"), value)

    def set(self, value):
        if value is None:  # sama seperti firebase_admin
            raise ValueError("Value must not be None.")
        self.db.set_path(self.parts, value)

    def delete(self):
        self.db.set_path(self.parts, None)
