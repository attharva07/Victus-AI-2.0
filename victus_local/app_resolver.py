from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Tuple

from .app_aliases import list_known_apps, normalize_app_name
from .app_dictionary import AppDictionary, load_app_dictionary


_OPEN_PREFIX_RE = re.compile(r"^(open|launch|start|run)\s+", re.IGNORECASE)
_OPEN_ARTICLE_RE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class ResolvedCandidate:
    name: str
    target: str
    score: float


@dataclass(frozen=True)
class AppResolutionResult:
    match: Optional[ResolvedCandidate]
    confidence: float
    candidates: List[ResolvedCandidate]


def resolve_app_name(text: str, app_index: AppDictionary | None = None) -> AppResolutionResult:
    dictionary = app_index or load_app_dictionary()
    normalized = normalize_app_name(extract_app_phrase(text))
    if not normalized:
        return AppResolutionResult(match=None, confidence=0.0, candidates=[])

    alias_map = dictionary.alias_map()
    exact_target = alias_map.get(normalized)
    if exact_target:
        label = _label_for_target(exact_target, dictionary) or normalized.title()
        match = ResolvedCandidate(name=label, target=exact_target, score=1.0)
        return AppResolutionResult(match=match, confidence=1.0, candidates=[match])

    entries = _build_candidate_entries(dictionary)
    for entry_name, entry_target in entries:
        if normalize_app_name(entry_name) == normalized:
            label = _label_for_target(entry_target, dictionary) or entry_name
            match = ResolvedCandidate(name=label, target=entry_target, score=1.0)
            return AppResolutionResult(match=match, confidence=1.0, candidates=[match])

    partial_targets: Dict[str, ResolvedCandidate] = {}
    for entry_name, entry_target in entries:
        entry_normalized = normalize_app_name(entry_name)
        if normalized and normalized in entry_normalized:
            label = _label_for_target(entry_target, dictionary) or entry_name
            partial_targets[entry_target] = ResolvedCandidate(name=label, target=entry_target, score=0.9)
    if len(partial_targets) == 1:
        match = next(iter(partial_targets.values()))
        return AppResolutionResult(match=match, confidence=match.score, candidates=[match])

    scored = _score_candidates(normalized, entries, dictionary)
    if not scored:
        return AppResolutionResult(match=None, confidence=0.0, candidates=[])
    best = scored[0]
    return AppResolutionResult(match=best, confidence=best.score, candidates=scored)


def resolve_from_candidates(
    text: str,
    candidates: Iterable[ResolvedCandidate],
    app_index: AppDictionary | None = None,
) -> Optional[ResolvedCandidate]:
    normalized = normalize_app_name(text)
    entries = list(candidates)
    if not normalized or not entries:
        return None
    if normalized.isdigit():
        index = int(normalized) - 1
        if 0 <= index < len(entries):
            return entries[index]
        return None

    for candidate in entries:
        if normalize_app_name(candidate.name) == normalized:
            return candidate

    dictionary = app_index or load_app_dictionary()
    alias_target = dictionary.alias_map().get(normalized)
    if alias_target:
        for candidate in entries:
            if candidate.target.lower() == alias_target.lower():
                return candidate

    best = _best_fuzzy_match(normalized, [(entry.name, entry.target) for entry in entries])
    if best and best.score >= 0.6:
        return best
    return None


def build_clarify_candidates(candidates: Iterable[ResolvedCandidate]) -> List[Dict[str, str]]:
    return [{"label": candidate.name, "target": candidate.target} for candidate in candidates]


def build_candidate_prompt(candidates: Iterable[ResolvedCandidate]) -> str:
    entries = list(candidates)
    if not entries:
        return "Which app should I open?"
    choices = " ".join(f"({idx}) {entry.name}" for idx, entry in enumerate(entries, start=1))
    return f"Which app should I open? {choices}"


def extract_app_phrase(text: str) -> str:
    value = text.strip()
    if not value:
        return ""
    value = _OPEN_PREFIX_RE.sub("", value).strip()
    value = _OPEN_ARTICLE_RE.sub("", value).strip()
    return value


def _build_candidate_entries(dictionary: AppDictionary) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []
    for app in list_known_apps():
        entries.append((app.label, app.target))
        entries.append((app.target, app.target))
        for alias in app.aliases:
            entries.append((alias, app.target))

    for alias, target in dictionary.alias_map().items():
        entries.append((alias, target))

    for target, entry in dictionary.canonical.items():
        label = entry.get("label") if isinstance(entry, dict) else None
        if isinstance(label, str) and label.strip():
            entries.append((label, target))
        entries.append((target, target))

    deduped: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for name, target in entries:
        normalized = normalize_app_name(name)
        if not normalized:
            continue
        key = (normalized, target.lower())
        if key not in deduped:
            deduped[key] = (name, target)
    return list(deduped.values())


def _score_candidates(
    normalized: str,
    entries: Iterable[Tuple[str, str]],
    dictionary: AppDictionary,
) -> List[ResolvedCandidate]:
    best_by_target: Dict[str, ResolvedCandidate] = {}
    for name, target in entries:
        score = _similarity(normalized, normalize_app_name(name))
        if target not in best_by_target or score > best_by_target[target].score:
            label = _label_for_target(target, dictionary) or name
            best_by_target[target] = ResolvedCandidate(name=label, target=target, score=score)

    scored = sorted(best_by_target.values(), key=lambda candidate: candidate.score, reverse=True)
    return scored[:3]


def _best_fuzzy_match(normalized: str, entries: Iterable[Tuple[str, str]]) -> Optional[ResolvedCandidate]:
    best: Optional[ResolvedCandidate] = None
    for name, target in entries:
        score = _similarity(normalized, normalize_app_name(name))
        if not best or score > best.score:
            best = ResolvedCandidate(name=name, target=target, score=score)
    return best


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ratio = SequenceMatcher(None, a, b).ratio()
    if a in b:
        length_ratio = min(len(a) / max(len(b), 1), 1.0)
        substring_score = 0.6 + (0.4 * length_ratio)
        return max(ratio, substring_score)
    return ratio


def _label_for_target(target: str, dictionary: AppDictionary) -> Optional[str]:
    for app in list_known_apps():
        if app.target.lower() == target.lower():
            return app.label
    entry = dictionary.canonical.get(target)
    if isinstance(entry, dict):
        label = entry.get("label")
        if isinstance(label, str) and label.strip():
            return label
    return None
