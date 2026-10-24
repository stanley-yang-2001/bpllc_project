"""Display preferences kept on the account (M8p, design 3H)."""
import pytest

from conftest import register
from test_account import db

COLORS = {"page": "#eef6ff", "cards": "#ffffff", "text": "#0b2540", "borders": "#c9dcf0", "accent": "#0369a1"}


def patch(client, **body):
    return client.patch("/api/me/preferences", json=body)


def test_no_row_means_null_preferences(client):
    register(client, "alice")
    assert client.get("/api/me").json()["preferences"] is None
    assert db("SELECT count(*) FROM tutor.user_preferences")[0][0] == 0           # reading never creates a row


def test_first_save_creates_the_row_with_defaults_for_the_rest(client):
    register(client, "alice")
    r = patch(client, theme="dark")
    assert r.status_code == 200
    assert r.json() == {"active_language": None, "ui_follows_study_language": False, "chat_in_study_language": False, "theme": "dark", "custom_colors": None}
    assert client.get("/api/me").json()["preferences"] == r.json()


def test_partial_updates_leave_the_other_fields_alone(client):
    register(client, "alice")
    client.post("/api/me/languages", json={"language": "es"})
    patch(client, theme="ocean", custom_colors=COLORS, ui_follows_study_language=True, active_language="es")
    r = patch(client, theme="forest")
    assert r.json() == {"active_language": "es", "ui_follows_study_language": True, "chat_in_study_language": False, "theme": "forest", "custom_colors": COLORS}
    r = patch(client, ui_follows_study_language=False)
    assert r.json()["theme"] == "forest" and r.json()["custom_colors"] == COLORS and r.json()["ui_follows_study_language"] is False


def test_an_empty_patch_is_accepted_and_changes_nothing(client):
    register(client, "alice")
    patch(client, theme="midnight")
    assert patch(client).json()["theme"] == "midnight"


def test_null_clears_the_active_language_and_the_custom_colors(client):
    register(client, "alice")
    patch(client, active_language="en", custom_colors=COLORS)
    r = patch(client, active_language=None, custom_colors=None)
    assert r.json()["active_language"] is None and r.json()["custom_colors"] is None


def test_custom_colors_are_kept_while_another_theme_is_selected(client):
    register(client, "alice")
    patch(client, theme="custom", custom_colors=COLORS)
    assert patch(client, theme="light").json()["custom_colors"] == COLORS


def test_colors_are_stored_in_lowercase(client):
    register(client, "alice")
    r = patch(client, custom_colors={**COLORS, "accent": "#0369A1"})
    assert r.json()["custom_colors"]["accent"] == "#0369a1"


@pytest.mark.parametrize("theme", ["Dark", "1dark", "", "a" * 25, "dark mode", "dark;drop", "ocean_blue"])
def test_a_badly_shaped_theme_id_is_refused(client, theme):
    register(client, "alice")
    r = patch(client, theme=theme)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_the_server_accepts_a_theme_id_it_does_not_know(client):
    """The server checks the shape only: the app decides what an id means, so an older app and a newer server coexist."""
    register(client, "alice")
    assert patch(client, theme="some-future-preset").status_code == 200


@pytest.mark.parametrize("accent", ["red", "#fff", "#12345", "#1234567", "0369a1", "#gggggg", "#0369a1 ", "rgb(1,2,3)"])
def test_a_bad_color_is_refused(client, accent):
    register(client, "alice")
    r = patch(client, custom_colors={**COLORS, "accent": accent})
    assert r.status_code == 422


def test_a_missing_or_extra_color_part_is_refused(client):
    register(client, "alice")
    assert patch(client, custom_colors={k: v for k, v in COLORS.items() if k != "text"}).status_code == 422
    assert patch(client, custom_colors={**COLORS, "sidebar": "#000000"}).status_code == 422


def test_unknown_keys_are_rejected(client):
    register(client, "alice")
    assert patch(client, themme="dark").status_code == 422
    assert patch(client, user_id=2).status_code == 422


def test_null_is_refused_for_a_field_that_always_has_a_value(client):
    register(client, "alice")
    assert patch(client, theme=None).status_code == 422
    assert patch(client, ui_follows_study_language=None).status_code == 422


def test_the_active_language_must_be_one_of_the_learners_languages(client):
    register(client, "alice")                                       # studies English only
    r = patch(client, active_language="es")
    assert r.status_code == 422 and "not one of your languages" in r.json()["error"]["message"]
    assert patch(client, active_language="xx").status_code == 422
    client.post("/api/me/languages", json={"language": "es"})
    assert patch(client, active_language="es").status_code == 200


def test_preferences_need_a_login(client):
    assert client.patch("/api/me/preferences", json={"theme": "dark"}).status_code == 401


def test_one_learner_can_neither_read_nor_change_anothers(client, make_user):
    register(client, "alice")
    patch(client, theme="forest", custom_colors=COLORS)
    bob = make_user("bob")
    assert bob.get("/api/me").json()["preferences"] is None
    assert patch(bob, theme="rose").json()["theme"] == "rose"
    assert client.get("/api/me").json()["preferences"]["theme"] == "forest"
    assert client.get("/api/me").json()["preferences"]["custom_colors"] == COLORS


def test_other_profile_responses_carry_the_preferences_too(client):
    register(client, "alice")
    patch(client, theme="graphite")
    r = client.patch("/api/me", json={"display_name": "Alicia"})
    assert r.json()["preferences"]["theme"] == "graphite"


def test_the_export_contains_the_preferences(client):
    register(client, "alice")
    assert client.get("/api/me/export").json()["user_preferences"] is None
    patch(client, theme="sunset", custom_colors=COLORS)
    saved = client.get("/api/me/export").json()["user_preferences"]
    assert saved["theme"] == "sunset" and saved["custom_colors"] == COLORS and "updated_at" in saved


def test_deleting_the_account_removes_the_preferences(client, make_user):
    register(client, "alice")
    patch(client, theme="sunset")
    bob = make_user("bob")
    patch(bob, theme="rose")
    client.post("/api/me/delete", json={"password": "password123"})
    assert db("SELECT theme FROM tutor.user_preferences") == [("rose",)]


def test_the_database_itself_refuses_a_bad_theme(client):
    import psycopg2
    register(client, "alice")
    with pytest.raises(psycopg2.errors.CheckViolation):
        db("INSERT INTO tutor.user_preferences (user_id, theme) VALUES (1, 'Not Valid')")


def test_chat_in_study_language_is_off_by_default_saved_alone_and_never_null(client):
    register(client, "alice")
    r = patch(client, theme="dark")
    assert r.json()["chat_in_study_language"] is False
    r = patch(client, chat_in_study_language=True)
    assert r.json()["chat_in_study_language"] is True and r.json()["theme"] == "dark"
    assert patch(client, theme="forest").json()["chat_in_study_language"] is True        # other saves leave it alone
    assert patch(client, chat_in_study_language=None).status_code == 422
