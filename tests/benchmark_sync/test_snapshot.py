import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.benchmark_sync.snapshot import publish_files, read_central, unpack, validate_payload, canonical, digest, snapshot_id
from src.benchmark_sync.delta import pack_delta, unpack_delta


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "ledger.sqlite3"
        with closing(sqlite3.connect(self.db)) as db, db:
            db.executescript("CREATE TABLE records(seq INTEGER, id TEXT, body TEXT); CREATE TABLE events(seq INTEGER,kind TEXT,body TEXT); CREATE TABLE sources(id TEXT,body TEXT);")
        self.add(1)

    def tearDown(self):
        self.temp.cleanup()

    def add(self, n):
        record = dict(id=f"{n:064x}", attempt_id=f"attempt-{n}", revision=1,
                      problem="P1", case_id="001", cores=1, metrics={"makespan_cycles": n}, eligible=True)
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("INSERT INTO records VALUES(?,?,?)", (n, record["id"], json.dumps(record)))
            db.execute("INSERT INTO events VALUES(?,?,?)", (n, "record", json.dumps({"id": record["id"]})))

    def read(self):
        return read_central(self.db, frozen_manifest={}, algorithms={}, code_commit="a" * 40)

    def test_roundtrip_and_unchanged(self):
        output = self.root / "published"
        payload = self.read()
        manifest = publish_files(payload, output)
        self.assertEqual(unpack((output / manifest["payload_file"]).read_bytes(), manifest), payload)
        self.assertTrue(publish_files(self.read(), output)["unchanged"])
        self.add(2)
        self.assertEqual(publish_files(self.read(), output)["record_count"], 2)

    def test_delta_reconstructs_exact_append_and_rejects_wrong_base(self):
        base=self.read();self.add(2);target=self.read()
        data=pack_delta(base,target)
        self.assertEqual(unpack_delta(base,data),target)
        self.assertIsNone(pack_delta(target,target))
        with self.assertRaisesRegex(ValueError,'base or shape'):
            unpack_delta(target,data)
        forged=bytearray(data);forged[-5]^=1
        with self.assertRaises(ValueError): unpack_delta(base,bytes(forged))

    def test_delta_cannot_rewrite_old_record(self):
        base=self.read();self.add(2);target=self.read()
        target['records'][0]['metrics']['makespan_cycles']=900
        target['records_sha256']=digest(canonical(target['records']))
        target['snapshot_id']=snapshot_id(target)
        with self.assertRaisesRegex(ValueError,'rewrote'):
            pack_delta(base,target)

    def test_missing_history_cannot_replace_last_good(self):
        output = self.root / "published"
        manifest = publish_files(self.read(), output)
        saved = (output / "current.json").read_bytes()
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("DELETE FROM records")
            db.execute("DELETE FROM events")
        with self.assertRaises(ValueError):
            publish_files(self.read(), output)
        self.assertEqual((output / "current.json").read_bytes(), saved)
        self.assertEqual(unpack((output / manifest["payload_file"]).read_bytes(), manifest)["record_count"], 1)

    def test_rewritten_history_rejected_even_with_advanced_cursor(self):
        output = self.root / "published"
        publish_files(self.read(), output)
        with closing(sqlite3.connect(self.db)) as db, db:
            r = json.loads(db.execute("SELECT body FROM records").fetchone()[0])
            r["metrics"]["makespan_cycles"] = 900
            db.execute("UPDATE records SET body=?", (json.dumps(r),))
        self.add(2)
        with self.assertRaisesRegex(ValueError, "rewrote"):
            publish_files(self.read(), output)

    def test_damaged_event_history_fails_closed(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("DELETE FROM events")
        with self.assertRaisesRegex(ValueError, "event/history"):
            self.read()

    def test_bad_hash_or_size_rejected(self):
        output = self.root / "published"
        manifest = publish_files(self.read(), output)
        data = (output / manifest["payload_file"]).read_bytes()
        with self.assertRaises(ValueError):
            unpack(data + b"x", manifest)
        changed = dict(manifest, decoded_size=1)
        with self.assertRaises(ValueError):
            unpack(data, changed)

    def test_bad_json_shapes_and_semantic_forgery(self):
        for value in (None, [], 1, {"schema_version":1,"sequence":1,"records":[None]}):
            with self.assertRaises(ValueError): validate_payload(value)
        for value in (None,[],1):
            with self.assertRaises(ValueError): unpack(b"",value)
        for field,value in [('source_status',[]),('source_status',{'x':None}),('publisher',[]),('algorithms',None),('generated_at',0)]:
            payload=self.read(); payload[field]=value
            with self.assertRaises(ValueError): validate_payload(payload)
        payload=self.read(); payload['publisher']['board_code_commit']='b'*40
        with self.assertRaisesRegex(ValueError,'semantic'): validate_payload(payload)
        payload=self.read(); payload['records'][0]['sequence']=0
        payload['records_sha256']=digest(canonical(payload['records']))
        payload['snapshot_id']=snapshot_id(payload)
        with self.assertRaisesRegex(ValueError,'sequence'): validate_payload(payload)

    def test_wrong_path_does_not_create_authority(self):
        missing = self.root / "missing.sqlite3"
        with self.assertRaises(sqlite3.OperationalError):
            read_central(missing, frozen_manifest={}, algorithms={}, code_commit="a" * 40)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
