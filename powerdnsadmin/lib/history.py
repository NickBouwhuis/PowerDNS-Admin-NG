"""History changelog utilities.

Extracts record-level change information from History model entries
for display in the domain changelog UI.
"""
import json


def get_record_changes(del_rrset, add_rrset):
    """Use the given deleted and added RRset to build a list of record changes.

    Args:
        del_rrset: The RRset with changetype DELETE, or None
        add_rrset: The RRset with changetype REPLACE, or None

    Returns:
        A list of tuples in the format ``(old_state, new_state, change_type)``.
        ``old_state`` and ``new_state`` are dictionaries with the keys
        "disabled", "content" and "comment".  ``change_type`` can be
        "addition", "deletion", "edit" or "unchanged".  When it's "addition"
        then ``old_state`` is None, when it's "deletion" then ``new_state``
        is None.
    """

    def get_records(rrset):
        """For the given RRset return a combined list of records and comments."""
        if not rrset or 'records' not in rrset:
            return []
        records = [dict(record) for record in rrset['records']]
        for i, record in enumerate(records):
            if 'comments' in rrset and len(rrset['comments']) > i:
                record['comment'] = rrset['comments'][i].get('content', None)
            else:
                record['comment'] = None
        return records

    def record_is_unchanged(old, new):
        """Returns True if the old record is not different from the new one."""
        if old['content'] != new['content']:
            raise ValueError("Can't compare records with different content")
        return old['disabled'] == new['disabled'] and old['comment'] == new['comment']

    def to_state(record):
        """For the given record, return the state dict."""
        return {
            "disabled": record['disabled'],
            "content": record['content'],
            "comment": record.get('comment', ''),
        }

    add_records = get_records(add_rrset)
    del_records = get_records(del_rrset)
    changeset = []

    for add_record in add_records:
        for del_record in list(del_records):
            if add_record['content'] == del_record['content']:
                if record_is_unchanged(del_record, add_record):
                    changeset.append((to_state(del_record), to_state(add_record), "unchanged"))
                else:
                    changeset.append((to_state(del_record), to_state(add_record), "edit"))
                del_records.remove(del_record)
                break
        else:
            changeset.append((None, to_state(add_record), "addition"))

    for del_record in del_records:
        changeset.append((to_state(del_record), None, "deletion"))

    changeset.sort(key=lambda change: change[0]['content'] if change[0] else change[1]['content'])

    return changeset


def filter_rr_list_by_name_and_type(rrset, record_name, record_type):
    """Filter an RRset list to entries matching the given name and type."""
    return list(filter(
        lambda rr: rr['name'] == record_name and rr['type'] == record_type,
        rrset,
    ))


def extract_changelogs_from_history(histories, record_name=None, record_type=None):
    """Extract record-level changelog entries from a list of History objects.

    Args:
        histories: Iterable of History model instances.
        record_name: Optional filter for a specific record name.
        record_type: Optional filter for a specific record type.

    Returns:
        A list of :class:`HistoryRecordEntry` objects sorted by record name.
    """
    out_changes = []

    for entry in histories:
        changes = []

        if entry.detail is None:
            continue

        if "add_rrsets" in entry.detail:
            details = json.loads(entry.detail)
            if not details['add_rrsets'] and not details['del_rrsets']:
                continue
        else:
            continue

        if record_name is not None and record_type is not None:
            details['add_rrsets'] = list(
                filter_rr_list_by_name_and_type(details['add_rrsets'], record_name, record_type))
            details['del_rrsets'] = list(
                filter_rr_list_by_name_and_type(details['del_rrsets'], record_name, record_type))

            if not details['add_rrsets'] and not details['del_rrsets']:
                continue

        del_add_changes = set(
            [(r['name'], r['type']) for r in details['add_rrsets']]
        ).intersection(
            [(r['name'], r['type']) for r in details['del_rrsets']]
        )
        for del_add_change in del_add_changes:
            changes.append(HistoryRecordEntry(
                entry,
                filter_rr_list_by_name_and_type(
                    details['del_rrsets'], del_add_change[0], del_add_change[1]
                ).pop(0),
                filter_rr_list_by_name_and_type(
                    details['add_rrsets'], del_add_change[0], del_add_change[1]
                ).pop(0),
                "*",
            ))

        for rrset in details['add_rrsets']:
            if (rrset['name'], rrset['type']) not in del_add_changes:
                changes.append(HistoryRecordEntry(entry, {}, rrset, "+"))

        for rrset in details['del_rrsets']:
            if (rrset['name'], rrset['type']) not in del_add_changes:
                changes.append(HistoryRecordEntry(entry, rrset, {}, "-"))

        if changes:
            changes.sort(
                key=lambda change: change.del_rrset['name']
                if change.del_rrset else change.add_rrset['name']
            )
            out_changes.extend(changes)

    return out_changes


class HistoryRecordEntry:
    """A changelog entry representing a pair of add/del RRsets.

    Attributes:
        history_entry: The parent History model instance.
        add_rrset: Dict of the REPLACE RRset (or empty dict).
        del_rrset: Dict of the DELETE RRset (or empty dict).
        change_type: ``"*"`` (edit/unchanged), ``"+"`` (new), or ``"-"`` (deleted).
        changed_fields: Subset of ``["ttl", "name", "type"]``.
        changeSet: List of per-record change tuples from :func:`get_record_changes`.
    """

    def __init__(self, history_entry, del_rrset, add_rrset, change_type):
        self.history_entry = history_entry
        self.add_rrset = add_rrset
        self.del_rrset = del_rrset
        self.change_type = change_type
        self.changed_fields = []
        self.changeSet = []

        if change_type in ("+", "-"):
            self.changed_fields.append("name")
            self.changed_fields.append("type")
            self.changed_fields.append("ttl")
        elif change_type == "*":
            if add_rrset['ttl'] != del_rrset['ttl']:
                self.changed_fields.append("ttl")

        self.changeSet = get_record_changes(del_rrset, add_rrset)

    def toDict(self):
        return {
            "add_rrset": self.add_rrset,
            "del_rrset": self.del_rrset,
            "changed_fields": self.changed_fields,
            "created_on": self.history_entry.created_on,
            "created_by": self.history_entry.created_by,
            "change_type": self.change_type,
            "changeSet": self.changeSet,
        }

    def __eq__(self, obj2):
        return self.toDict() == obj2.toDict()
