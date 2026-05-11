import pytest
from pathlib import Path
from db.repository import AppRepository


@pytest.fixture
def repo(tmp_path):
    return AppRepository(db_path=tmp_path / "test.db")


async def test_save_and_load_credentials(repo):
    await repo.init()
    payload = {"MUSIC_U": "abc123", "__csrf": "xyz"}
    await repo.save_credential("netease", payload)
    loaded = await repo.load_credential("netease")
    assert loaded == payload
    await repo.close()


async def test_load_missing_credential_returns_none(repo):
    await repo.init()
    assert await repo.load_credential("netease") is None
    await repo.close()


async def test_overwrite_credential(repo):
    await repo.init()
    await repo.save_credential("netease", {"old": "value"})
    await repo.save_credential("netease", {"new": "value"})
    loaded = await repo.load_credential("netease")
    assert loaded == {"new": "value"}
    await repo.close()


async def test_credential_is_encrypted_at_rest(repo):
    await repo.init()
    await repo.save_credential("netease", {"secret": "s3cr3t"})
    async with repo._db.execute(
        "SELECT data FROM credentials WHERE platform = ?", ("netease",)
    ) as cur:
        row = await cur.fetchone()
    assert b"s3cr3t" not in row[0]
    await repo.close()
