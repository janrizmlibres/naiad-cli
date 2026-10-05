"""The short form an Entry is shown by, and what a short form names.

An Entry id is a timestamp, the Workflow's name and a process id. The process
id ends it and is what tells most Entries apart, but not all: an agent queueing
a night's work in one turn gives every Entry the same one, and a Run's id ends
in the same number as its Entry's. So a short form is the fewest trailing parts
of the id no other id ends in, and a name is taken as the id it equals, else as
every id it ends.
"""

from naiad.domain.short_ids import named_by, short_ids

PARENT = "20261005-012208-211125-matt-pocock-51695"
CHILD = "20261005-012443-573056-matt-pocock-56055"
SIBLING = "20261005-012443-573057-matt-pocock-56055"


def test_an_id_is_shown_by_its_process_id_when_no_other_ends_in_it():
    assert short_ids([PARENT, CHILD]) == {PARENT: "51695", CHILD: "56055"}


def test_ids_sharing_a_process_id_are_lengthened_until_they_differ():
    shown = short_ids([PARENT, CHILD, SIBLING])

    assert shown[PARENT] == "51695"
    assert shown[CHILD] == "573056-matt-pocock-56055"
    assert shown[SIBLING] == "573057-matt-pocock-56055"


def test_an_id_another_ends_in_is_shown_whole():
    assert short_ids(["held", "1-held"]) == {"held": "held", "1-held": "1-held"}


def test_a_lone_id_is_shown_by_its_last_part():
    assert short_ids([PARENT]) == {PARENT: "51695"}


def test_a_short_form_names_the_one_id_it_was_shown_for():
    ids = [PARENT, CHILD, SIBLING]

    for full, short in short_ids(ids).items():
        assert named_by(ids, short) == [full]


def test_a_full_id_names_itself_even_when_another_ends_in_it():
    assert named_by(["held", "1-held"], "held") == ["held"]


def test_a_name_ending_several_ids_names_them_all():
    assert named_by([PARENT, CHILD, SIBLING], "56055") == [CHILD, SIBLING]


def test_a_name_is_matched_on_whole_parts_only():
    assert named_by([PARENT], "1695") == []
    assert named_by([PARENT], "pocock-516") == []


def test_an_empty_name_names_nothing():
    assert named_by([PARENT], "") == []
