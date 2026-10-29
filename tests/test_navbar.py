"""The loaded campaign is shown as a distinct chip, not as another menu item."""

from __future__ import annotations

from app.services import campaign_service


def test_loaded_campaign_chip_is_separate_from_menu_links(client, minimal_force):
    campaign = campaign_service.create_campaign_from_force(
        minimal_force, "Draconis Reach", starting_bt_year=3151, starting_bt_month=1
    )
    html = client.get("/campaigns").data.decode()
    nav = html[html.index("<nav") : html.index("</nav>")]
    assert "navbar-campaign" in nav
    assert "Draconis Reach" in nav
    assert "Chaos" in nav  # ruleset badge
    # Not rendered as one of the nav-link menu entries.
    assert f'class="nav-link" href="/campaigns/{campaign.id}"' not in nav


def test_no_chip_without_a_loaded_campaign(client):
    html = client.get("/campaigns").data.decode()
    nav = html[html.index("<nav") : html.index("</nav>")]
    assert "navbar-campaign" not in nav


def test_campaign_sheet_cards_have_a_grey_header_style(client, minimal_force):
    campaign = campaign_service.create_campaign_from_force(
        minimal_force, "Grey", starting_bt_year=3151, starting_bt_month=1
    )
    html = client.get(f"/campaigns/{campaign.id}").data.decode()
    assert ".campaign-sheet .card > .card-header" in html
    assert "background-color: #ced4da !important" in html
    assert 'class="campaign-sheet"' in html
    assert html.index('class="campaign-sheet"') < html.index('<div class="card-header')


def test_pages_keep_scroll_position_after_a_form_post(client):
    html = client.get("/campaigns").data.decode()
    assert "mechbay.scroll" in html
    assert "window.scrollTo(0, saved.y)" in html
