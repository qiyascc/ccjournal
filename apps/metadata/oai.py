# ==========================================================
#
# █▀█ █ █▄█ ▄▀█ █▀  █▀▀ █▀▀
# ▀▀█ █ ░█░ █▀█ ▄█  █▄▄ █▄▄
#
# Project     : CC Journal
# Developed by: Qiyas CC
# Copyright © 2026 Qiyas CC
# All Rights Reserved.
# ==========================================================

"""
OAI-PMH 2.0 sağlayıcı motoru.

6 verb: Identify, ListMetadataFormats, ListSets, ListIdentifiers, ListRecords,
GetRecord. Resumption token (durumsuz, offset tabanlı), silinen kayıt desteği
(Tombstone), from/until tarih süzme, set = bölüm (section).
"""
from __future__ import annotations

import base64
import datetime as dt
import json

from django.conf import settings
from django.utils import timezone
from lxml import etree

from apps.journals.models import Journal
from apps.submissions.models import Submission, SubmissionStatus
from .models import Tombstone
from .serializers import NS, OAI_FORMATS, _sub

OAI_NS = "http://www.openarchives.org/OAI/2.0/"
GRANULARITY = "YYYY-MM-DDThh:mm:ssZ"


def _conf():
    base = dict(getattr(settings, "OAI", {}))
    try:
        from apps.configuration.services import Config
        base["repository_name"] = Config.get("oai", "repository_name", base.get("repository_name"))
        base["admin_email"] = Config.get("oai", "admin_email", base.get("admin_email"))
        base["repository_identifier"] = Config.get(
            "oai", "repository_id", base.get("repository_identifier"))
    except Exception:
        pass
    return base


def repository_id() -> str:
    return _conf().get("repository_identifier", "ccjournal.local")


def oai_identifier(journal_path: str, submission_id: int) -> str:
    return f"oai:{repository_id()}:{journal_path}/{submission_id}"


def _fmt(d: dt.datetime) -> str:
    if timezone.is_aware(d):
        d = d.astimezone(dt.UTC)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(value: str):
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class OAIError(Exception):
    def __init__(self, code, message=""):
        self.code = code
        self.message = message


class OAIProvider:
    PAGE_SIZE = property(lambda self: _conf().get("page_size", 50))

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.journal = Journal.current()
        from apps.plugins.hooks import hooks
        self.formats = hooks.apply_filters("oai.formats", dict(OAI_FORMATS))


    def handle(self, params: dict) -> etree.Element:
        verb = params.get("verb")
        try:
            if verb == "Identify":
                return self._envelope(params, self._identify())
            if verb == "ListMetadataFormats":
                return self._envelope(params, self._list_metadata_formats(params))
            if verb == "ListSets":
                return self._envelope(params, self._list_sets())
            if verb == "GetRecord":
                return self._envelope(params, self._get_record(params))
            if verb in ("ListIdentifiers", "ListRecords"):
                return self._envelope(params, self._list(params, records=(verb == "ListRecords")))
            raise OAIError("badVerb", "Illegal or missing verb.")
        except OAIError as e:
            return self._error_envelope(params, e)


    def _root(self):
        return etree.Element(
            _q_oai("OAI-PMH"),
            {f"{{{NS['xsi']}}}schemaLocation":
                f"{OAI_NS} http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd"},
            nsmap={None: OAI_NS, "xsi": NS["xsi"]},
        )

    def _envelope(self, params, payload):
        root = self._root()
        _sub(root, _q_oai("responseDate"), _fmt(timezone.now()))
        req = _sub(root, _q_oai("request"), self.base_url)
        for k in ("verb", "identifier", "metadataPrefix", "from", "until", "set"):
            if params.get(k):
                req.set(k, params[k])
        root.append(payload)
        return root

    def _error_envelope(self, params, err: OAIError):
        root = self._root()
        _sub(root, _q_oai("responseDate"), _fmt(timezone.now()))
        req = _sub(root, _q_oai("request"), self.base_url)
        if err.code not in ("badVerb", "badArgument"):
            for k in ("verb", "identifier", "metadataPrefix", "from", "until", "set"):
                if params.get(k):
                    req.set(k, params[k])
        _sub(root, _q_oai("error"), err.message or err.code, code=err.code)
        return root


    def _identify(self):
        el = etree.Element(_q_oai("Identify"))
        c = _conf()
        _sub(el, _q_oai("repositoryName"), c.get("repository_name", "ccjournal"))
        _sub(el, _q_oai("baseURL"), self.base_url)
        _sub(el, _q_oai("protocolVersion"), "2.0")
        _sub(el, _q_oai("adminEmail"), c.get("admin_email", "admin@example.org"))
        _sub(el, _q_oai("earliestDatestamp"), self._earliest())
        _sub(el, _q_oai("deletedRecord"), "persistent")
        _sub(el, _q_oai("granularity"), GRANULARITY)
        return el

    def _earliest(self):
        first = Submission.objects.filter(
            status=SubmissionStatus.PUBLISHED).order_by("created_at").first()
        return _fmt(first.created_at) if first else "2000-01-01T00:00:00Z"

    def _list_metadata_formats(self, params):
        if params.get("identifier"):
            self._submission_from_identifier(params["identifier"])
        el = etree.Element(_q_oai("ListMetadataFormats"))
        for prefix, meta in self.formats.items():
            fmt = _sub(el, _q_oai("metadataFormat"))
            _sub(fmt, _q_oai("metadataPrefix"), prefix)
            _sub(fmt, _q_oai("schema"), meta["schema"])
            _sub(fmt, _q_oai("metadataNamespace"), meta["namespace"])
        return el

    def _list_sets(self):
        el = etree.Element(_q_oai("ListSets"))
        if not self.journal:
            raise OAIError("noSetHierarchy", "No journal configured.")
        for sec in self.journal.sections.all():
            s = _sub(el, _q_oai("set"))
            _sub(s, _q_oai("setSpec"), f"sec:{sec.id}")
            _sub(s, _q_oai("setName"), sec.tr_value("title") or f"Section {sec.id}")
        return el

    def _get_record(self, params):
        prefix = params.get("metadataPrefix")
        self._check_prefix(prefix)
        identifier = params.get("identifier")
        if not identifier:
            raise OAIError("badArgument", "Missing identifier.")
        el = etree.Element(_q_oai("GetRecord"))
        sub = self._submission_from_identifier(identifier)
        if sub:
            self._record(el, sub, prefix, records=True)
        else:
            tomb = Tombstone.objects.filter(oai_identifier=identifier).first()
            if not tomb:
                raise OAIError("idDoesNotExist", "No matching identifier.")
            self._deleted_record(el, tomb)
        return el

    def _list(self, params, *, records: bool):
        prefix = params.get("metadataPrefix")
        token = params.get("resumptionToken")
        if token:
            state = self._decode_token(token)
            prefix = state["prefix"]
            offset = state["offset"]
            frm, until, setspec = state.get("from"), state.get("until"), state.get("set")
        else:
            offset = 0
            frm, until, setspec = params.get("from"), params.get("until"), params.get("set")
        self._check_prefix(prefix)

        items = self._items(frm, until, setspec)
        if not items:
            raise OAIError("noRecordsMatch", "No records match the criteria.")

        page = items[offset:offset + self.PAGE_SIZE]
        verb = "ListRecords" if records else "ListIdentifiers"
        el = etree.Element(_q_oai(verb))
        for kind, obj in page:
            if kind == "live":
                self._record(el, obj, prefix, records=records)
            else:
                if records:
                    self._deleted_record(el, obj)
                else:
                    self._deleted_header(el, obj)

        next_offset = offset + self.PAGE_SIZE
        if next_offset < len(items):
            tok = self._encode_token(prefix, next_offset, frm, until, setspec)
            rt = _sub(el, _q_oai("resumptionToken"), tok)
            rt.set("completeListSize", str(len(items)))
            rt.set("cursor", str(offset))
        elif token:
            _sub(el, _q_oai("resumptionToken"), "")
        return el


    def _record(self, parent, submission, prefix, *, records):
        rec = _sub(parent, _q_oai("record"))
        self._header(rec, submission)
        if records:
            pub = submission.current_publication
            md = _sub(rec, _q_oai("metadata"))
            md.append(self.formats[prefix]["builder"](pub))

    def _header(self, parent, submission):
        h = _sub(parent, _q_oai("header"))
        _sub(h, _q_oai("identifier"), oai_identifier(submission.journal.path, submission.id))
        _sub(h, _q_oai("datestamp"), _fmt(submission.updated_at))
        pub = submission.current_publication
        if pub and pub.section_id:
            _sub(h, _q_oai("setSpec"), f"sec:{pub.section_id}")

    def _deleted_header(self, parent, tomb):
        h = _sub(parent, _q_oai("header"), status="deleted")
        _sub(h, _q_oai("identifier"), tomb.oai_identifier)
        _sub(h, _q_oai("datestamp"), _fmt(tomb.date_deleted))
        if tomb.set_spec:
            _sub(h, _q_oai("setSpec"), tomb.set_spec)

    def _deleted_record(self, parent, tomb):
        rec = _sub(parent, _q_oai("record"))
        self._deleted_header(rec, tomb)


    def _items(self, frm, until, setspec):
        qs = Submission.objects.filter(
            status=SubmissionStatus.PUBLISHED, current_publication__isnull=False)
        tqs = Tombstone.objects.all()
        if setspec:
            if not setspec.startswith("sec:"):
                raise OAIError("badArgument", "Unknown set.")
            sec_id = setspec.split(":", 1)[1]
            qs = qs.filter(current_publication__section_id=sec_id)
            tqs = tqs.filter(set_spec=setspec)
        if frm:
            d = _parse_dt(frm)
            if not d:
                raise OAIError("badArgument", "Bad 'from' date.")
            qs = qs.filter(updated_at__gte=d)
            tqs = tqs.filter(date_deleted__gte=d)
        if until:
            d = _parse_dt(until)
            if not d:
                raise OAIError("badArgument", "Bad 'until' date.")
            qs = qs.filter(updated_at__lte=d)
            tqs = tqs.filter(date_deleted__lte=d)

        items = [("live", s, s.updated_at) for s in qs.select_related("current_publication")]
        items += [("deleted", t, t.date_deleted) for t in tqs]
        items.sort(key=lambda x: (x[2], x[1].id))
        return [(kind, obj) for kind, obj, _ in items]


    def _check_prefix(self, prefix):
        if not prefix:
            raise OAIError("badArgument", "Missing metadataPrefix.")
        if prefix not in self.formats:
            raise OAIError("cannotDisseminateFormat", f"Unsupported format: {prefix}")

    def _submission_from_identifier(self, identifier):
        try:
            sub_id = int(identifier.rsplit("/", 1)[1])
        except (IndexError, ValueError):
            raise OAIError("idDoesNotExist", "Malformed identifier.")
        return Submission.objects.filter(
            id=sub_id, status=SubmissionStatus.PUBLISHED,
            current_publication__isnull=False).select_related("current_publication").first()

    def _encode_token(self, prefix, offset, frm, until, setspec):
        payload = {"prefix": prefix, "offset": offset,
                   "from": frm, "until": until, "set": setspec}
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

    def _decode_token(self, token):
        try:
            return json.loads(base64.urlsafe_b64decode(token.encode()).decode())
        except Exception:
            raise OAIError("badResumptionToken", "Invalid resumption token.")


def _q_oai(local: str) -> str:
    return f"{{{OAI_NS}}}{local}"
