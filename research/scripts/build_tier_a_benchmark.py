#!/usr/bin/env python3

from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "research" / "benchmark_v0.3"
OUT = BENCH / "data" / "tier_a_v0.3.1"

STRATA = [
    (
        "STR01",
        "Technology / software systems",
        [
            "Release Pipeline",
            "API Gateway",
            "Storage Service",
            "Notification Platform",
            "Monitoring Service",
            "Identity Platform",
        ],
        "Technology",
        "requests per minute",
        "backup capacity",
        "verification window",
        "production owner",
        "support window",
        "weekend maintenance window",
    ),
    (
        "STR02",
        "Healthcare / public health",
        [
            "Community Clinic",
            "Vaccination Center",
            "Diagnostic Lab",
            "Health Outreach Unit",
            "Rehabilitation Center",
            "Nutrition Program",
        ],
        "Healthcare",
        "appointments per weekday",
        "same-day reserve slots",
        "intake window",
        "service lead",
        "follow-up window",
        "Sunday operating period",
    ),
    (
        "STR03",
        "Finance / consumer finance",
        [
            "Savings Product",
            "Card Service",
            "Remittance Service",
            "Invoice Platform",
            "Budget Program",
            "Credit Education",
        ],
        "Finance",
        "units processed per day",
        "manual-review reserve",
        "processing window",
        "service owner",
        "support window",
        "weekend fee-waiver period",
    ),
    (
        "STR04",
        "Transportation / logistics",
        [
            "Metro Line",
            "Bus Network",
            "Freight Terminal",
            "Parcel Hub",
            "Bike Share",
            "Ferry Service",
        ],
        "Transportation",
        "units handled per departure",
        "standby capacity",
        "boarding cutoff",
        "operations lead",
        "customer-service window",
        "holiday service interval",
    ),
    (
        "STR05",
        "Education / training",
        [
            "Training Center",
            "University Course",
            "Language Program",
            "Certification Program",
            "Online Workshop",
            "Library Program",
        ],
        "Education",
        "standard seats",
        "reserve seats",
        "submission window",
        "program coordinator",
        "support window",
        "weekend enrollment period",
    ),
    (
        "STR06",
        "Environment / infrastructure",
        [
            "Water Facility",
            "Solar Site",
            "Recycling Center",
            "Flood Control Site",
            "Air Monitoring Station",
            "District Energy Plant",
        ],
        "Environment",
        "units monitored per day",
        "reserve capacity",
        "inspection window",
        "site manager",
        "reporting window",
        "holiday inspection period",
    ),
    (
        "STR07",
        "Public policy / administration",
        [
            "Permit Office",
            "Civic Service Desk",
            "Grant Program",
            "Housing Support",
            "Public Records Unit",
            "Community Advisory Board",
        ],
        "Public administration",
        "applications processed per day",
        "reserve processing capacity",
        "review period",
        "service coordinator",
        "public counter window",
        "weekend application period",
    ),
    (
        "STR08",
        "Consumer / operational information",
        [
            "Retail Service",
            "Home Maintenance",
            "Travel Pass",
            "Event Venue",
            "Delivery Subscription",
            "Meal Service",
        ],
        "Consumer operations",
        "orders handled per day",
        "same-day reserve capacity",
        "service window",
        "operations contact",
        "support window",
        "weekend cancellation period",
    ),
]

NAME_PREFIXES = [
    "Cedar",
    "Maple",
    "Harbor",
    "Northstar",
    "Juniper",
    "Riverside",
]

OWNER_NAMES = [
    "Operations Team",
    "Service Desk",
    "Program Office",
    "Site Operations",
    "Customer Operations",
    "Administrative Services",
]

TIME_WINDOWS = [
    "08:30-10:30",
    "09:00-11:00",
    "09:30-11:30",
    "10:00-12:00",
    "13:00-15:00",
    "14:00-16:00",
]

SUPPORT_WINDOWS = [
    "13:00-15:00",
    "14:00-16:00",
    "15:00-17:00",
    "16:00-18:00",
    "10:00-12:00",
    "11:00-13:00",
]

MISSING_BY_TYPE = {
    "semantic-paraphrase": "the exact Sunday closing time",
    "entity+attribute": "the direct contact email address",
    "distractor-heavy": "the weekend cancellation policy",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def jaccard_overlap(question: str, evidence: str) -> float:
    q = {
        token.strip(".,?!:;()[]{}\"'").lower()
        for token in question.split()
        if token.strip()
    }
    e = {
        token.strip(".,?!:;()[]{}\"'").lower()
        for token in evidence.split()
        if token.strip()
    }

    if not q or not e:
        return 0.0

    return len(q & e) / len(q | e)


def overlap_bucket(score: float) -> str:
    if score >= 0.40:
        return "high"
    if score >= 0.20:
        return "moderate"
    return "low"


def unit_texts(
    domain: str,
    topic: str,
    name: str,
    primary_value: int,
    reserve_value: int,
    verification_window: str,
    owner: str,
    support_window: str,
    weekend_period: str,
    primary_label: str,
    secondary_label: str,
    attribute_label: str,
    detail_label: str,
    distractor_label: str,
) -> list[str]:

    return [
        (
            f"{name} operates with a standard {primary_label} of "
            f"{primary_value} {primary_label.split()[-2] if primary_label.endswith('per day') else ''}."
        ).replace("  ", " ").strip()
        if primary_label.endswith("per day")
        else (
            f"{name} has a standard {primary_label} of {primary_value}."
        ),
        (
            f"The {topic.lower()} records a {attribute_label} of "
            f"{verification_window} for its normal service cycle."
        ),
        (
            f"The designated {detail_label} is {owner}, and the published "
            f"service detail is tied to the {name} unit."
        ),
        (
            f"A secondary record assigns {secondary_label} of {reserve_value} "
            f"to the same {name} operation."
        ),
        (
            f"The related {distractor_label} is listed for the "
            f"{name.lower()} service during {support_window}."
        ),
        (
            f"The broader {domain.lower()} context records a separate "
            f"weekend period of {weekend_period} for routine operations."
        ),
    ]


def main() -> None:
    if OUT.exists():
        raise SystemExit(
            f"REFUSING TO OVERWRITE EXISTING DIRECTORY: {OUT}"
        )

    OUT.mkdir(parents=True)

    documents: list[list[str]] = []
    queries: list[list[str]] = []
    qrels: list[list[str]] = []

    doc_specs: dict[str, dict] = {}

    doc_index = 0

    for (
        stratum_id,
        domain,
        topics,
        source_type,
        primary_label,
        secondary_label,
        attribute_label,
        detail_label,
        distractor_label,
        missing_attribute,
    ) in STRATA:

        for topic_index, topic in enumerate(topics):
            doc_index += 1

            doc_id = f"TIERA_{doc_index:03d}"
            version = "v1"
            name = f"{NAME_PREFIXES[topic_index]} {topic}"

            primary_value = 600 + (doc_index * 37)
            reserve_value = 120 + (doc_index * 11)

            verification_window = TIME_WINDOWS[
                topic_index
            ]

            owner = OWNER_NAMES[
                (doc_index - 1) % len(OWNER_NAMES)
            ]

            support_window = SUPPORT_WINDOWS[
                topic_index
            ]

            weekend_period = TIME_WINDOWS[
                (topic_index + 2) % len(TIME_WINDOWS)
            ]

            units = unit_texts(
                domain=domain,
                topic=topic,
                name=name,
                primary_value=primary_value,
                reserve_value=reserve_value,
                verification_window=verification_window,
                owner=owner,
                support_window=support_window,
                weekend_period=weekend_period,
                primary_label=primary_label,
                secondary_label=secondary_label,
                attribute_label=attribute_label,
                detail_label=detail_label,
                distractor_label=distractor_label,
            )

            # Conflict assignments are determined by the frozen allocation:
            # Q1 conflict -> docs 25-32
            # Q3 conflict -> docs 33-40
            # Q5 conflict -> docs 41-48
            conflict_type = None

            if 25 <= doc_index <= 32:
                conflict_type = "q1"
            elif 33 <= doc_index <= 40:
                conflict_type = "q3"
            elif 41 <= doc_index <= 48:
                conflict_type = "q5"

            conflict_primary = primary_value + 137
            conflict_time = (
                "15:00-17:00"
                if verification_window != "15:00-17:00"
                else "08:00-10:00"
            )
            conflict_support = (
                "18:00-20:00"
                if support_window != "18:00-20:00"
                else "09:00-11:00"
            )

            if conflict_type == "q1":
                units[3] = (
                    units[3]
                    + f" A separate entry in the same record lists the "
                    f"standard {primary_label} as {conflict_primary}."
                )

            elif conflict_type == "q3":
                units[5] = (
                    units[5]
                    + f" Another context entry lists the {attribute_label} "
                    f"as {conflict_time}."
                )

            elif conflict_type == "q5":
                units[4] = (
                    units[4]
                    + f" A separate service notice lists the {attribute_label} "
                    f"as {conflict_support}."
                )

            for unit_order, text in enumerate(units, start=1):
                unit_id = f"{doc_id}_U{unit_order:02d}"

                documents.append([
                    "controlled_tier_a_v0.3.1",
                    doc_id,
                    version,
                    unit_id,
                    unit_order,
                    sha256_text(text),
                    "synthetic",
                    "Aqlyra internally authored controlled benchmark content",
                    "CC0-equivalent internal test content",
                    text,
                ])

            doc_specs[doc_id] = {
                "domain": domain,
                "stratum_id": stratum_id,
                "topic": topic,
                "name": name,
                "primary_value": primary_value,
                "reserve_value": reserve_value,
                "verification_window": verification_window,
                "owner": owner,
                "support_window": support_window,
                "weekend_period": weekend_period,
                "primary_label": primary_label,
                "secondary_label": secondary_label,
                "attribute_label": attribute_label,
                "detail_label": detail_label,
                "distractor_label": distractor_label,
                "missing_attribute": missing_attribute,
                "conflict_type": conflict_type,
                "conflict_primary": conflict_primary,
                "conflict_time": conflict_time,
                "conflict_support": conflict_support,
            }

            # ---------------------------------------------------------
            # Five canonical questions per document
            # ---------------------------------------------------------
            base_q = (doc_index - 1) * 5

            # Q1
            q1_id = f"TIERA_Q{base_q + 1:03d}"

            if conflict_type == "q1":
                q1_answerability = "conflict"
                q1_answer = "Conflicting evidence; report uncertainty."
                q1_group = f"CG_{q1_id}"
                q1_rule = "report_uncertainty"
            else:
                q1_answerability = "answerable"
                q1_answer = str(primary_value)
                q1_group = ""
                q1_rule = ""

            q1 = (
                "What is the standard "
                f"{primary_label} for {name}?"
            )

            queries.append([
                "controlled_tier_a_v0.3.1",
                q1_id,
                doc_id,
                q1,
                "lexical-anchor",
                q1_answerability,
                q1_answer,
                "scope_demo",
                q1_group,
                q1_rule,
                2 if q1_answerability == "conflict" else 1,
                2,
                "high",
                "false",
                "draft",
                "Primary fact query; review lexical leakage and evidence alignment.",
            ])

            qrels.append([
                "controlled_tier_a_v0.3.1",
                q1_id,
                doc_id,
                version,
                f"{doc_id}_U01",
                2,
                units[0],
                "true" if q1_answerability == "conflict" else "false",
                q1_group,
                "",
            ])

            if q1_answerability == "conflict":
                qrels.append([
                    "controlled_tier_a_v0.3.1",
                    q1_id,
                    doc_id,
                    version,
                    f"{doc_id}_U04",
                    2,
                    units[3],
                    "true",
                    q1_group,
                    "",
                ])

            # Q2
            q2_id = f"TIERA_Q{base_q + 2:03d}"

            # First eight docs are unanswerable for q2.
            q2_unanswerable = doc_index <= 8

            if q2_unanswerable:
                q2_answerability = "unanswerable"
                q2_answer = ""
                q2_gold_count = 0
                q2_note = "Deliberately omitted attribute; no positive qrels."
            else:
                q2_answerability = "answerable"
                q2_answer = verification_window
                q2_gold_count = 1
                q2_note = "Paraphrase of the documented service attribute."

            q2_missing = doc_specs[doc_id]["missing_attribute"]

            q2 = (
                f"What timing applies to the normal service cycle of {name}?"
                if not q2_unanswerable
                else f"What is {q2_missing} for {name}?"
            )

            overlap = overlap_bucket(
                jaccard_overlap(
                    q2,
                    units[1],
                )
            ) if not q2_unanswerable else "low"

            queries.append([
                "controlled_tier_a_v0.3.1",
                q2_id,
                doc_id,
                q2,
                "semantic-paraphrase",
                q2_answerability,
                q2_answer,
                "scope_demo",
                "",
                "",
                q2_gold_count,
                3,
                overlap,
                "false",
                "draft",
                q2_note,
            ])

            if not q2_unanswerable:
                qrels.append([
                    "controlled_tier_a_v0.3.1",
                    q2_id,
                    doc_id,
                    version,
                    f"{doc_id}_U02",
                    2,
                    units[1],
                    "false",
                    "",
                    "",
                ])

            # Q3
            q3_id = f"TIERA_Q{base_q + 3:03d}"

            q3_unanswerable = 9 <= doc_index <= 16

            if conflict_type == "q3":
                q3_answerability = "conflict"
                q3_answer = "Conflicting evidence; report uncertainty."
                q3_group = f"CG_{q3_id}"
                q3_rule = "report_uncertainty"
                q3_gold_count = 2
            elif q3_unanswerable:
                q3_answerability = "unanswerable"
                q3_answer = ""
                q3_group = ""
                q3_rule = ""
                q3_gold_count = 0
            else:
                q3_answerability = "answerable"
                q3_answer = verification_window
                q3_group = ""
                q3_rule = ""
                q3_gold_count = 1

            if q3_unanswerable:
                q3 = (
                    f"What is the direct contact email address for {name}?"
                )
            else:
                q3 = (
                    f"What is the {attribute_label} recorded for {name}?"
                )

            queries.append([
                "controlled_tier_a_v0.3.1",
                q3_id,
                doc_id,
                q3,
                "entity+attribute",
                q3_answerability,
                q3_answer,
                "scope_demo",
                q3_group,
                q3_rule,
                q3_gold_count,
                2,
                "moderate",
                "false",
                "draft",
                "Entity-attribute query; review exact attribute wording.",
            ])

            if q3_answerability == "conflict":
                qrels.append([
                    "controlled_tier_a_v0.3.1",
                    q3_id,
                    doc_id,
                    version,
                    f"{doc_id}_U02",
                    2,
                    units[1],
                    "true",
                    q3_group,
                    "",
                ])
                qrels.append([
                    "controlled_tier_a_v0.3.1",
                    q3_id,
                    doc_id,
                    version,
                    f"{doc_id}_U06",
                    2,
                    units[5],
                    "true",
                    q3_group,
                    "",
                ])
            elif q3_answerability == "answerable":
                qrels.append([
                    "controlled_tier_a_v0.3.1",
                    q3_id,
                    doc_id,
                    version,
                    f"{doc_id}_U02",
                    2,
                    units[1],
                    "false",
                    "",
                    "",
                ])

            # Q4
            q4_id = f"TIERA_Q{base_q + 4:03d}"
            combined = primary_value + reserve_value

            q4 = (
                f"What is the combined operational capacity when the "
                f"standard {primary_label} of {primary_value} is added to "
                f"the {secondary_label} of {reserve_value} for {name}?"
            )

            queries.append([
                "controlled_tier_a_v0.3.1",
                q4_id,
                doc_id,
                q4,
                "multi-hop",
                "answerable",
                str(combined),
                "scope_demo",
                "",
                "",
                2,
                2,
                "moderate",
                "true",
                "draft",
                "Requires combining U01 and U04; review whether both units are necessary.",
            ])

            qrels.append([
                "controlled_tier_a_v0.3.1",
                q4_id,
                doc_id,
                version,
                f"{doc_id}_U01",
                2,
                units[0],
                "false",
                "",
                "",
            ])

            qrels.append([
                "controlled_tier_a_v0.3.1",
                q4_id,
                doc_id,
                version,
                f"{doc_id}_U04",
                2,
                units[3],
                "false",
                "",
                "",
            ])

            # Q5
            q5_id = f"TIERA_Q{base_q + 5:03d}"

            q5_unanswerable = 17 <= doc_index <= 24

            if conflict_type == "q5":
                q5_answerability = "conflict"
                q5_answer = "Conflicting evidence; report uncertainty."
                q5_group = f"CG_{q5_id}"
                q5_rule = "report_uncertainty"
                q5_gold_count = 2
            elif q5_unanswerable:
                q5_answerability = "unanswerable"
                q5_answer = ""
                q5_group = ""
                q5_rule = ""
                q5_gold_count = 0
            else:
                q5_answerability = "answerable"
                q5_answer = support_window
                q5_group = ""
                q5_rule = ""
                q5_gold_count = 1

            if q5_unanswerable:
                q5 = (
                    f"Which weekend cancellation policy is published for "
                    f"{name}?"
                )
            else:
                q5 = (
                    f"During which support window does the related service "
                    f"operate for {name}?"
                )

            queries.append([
                "controlled_tier_a_v0.3.1",
                q5_id,
                doc_id,
                q5,
                "distractor-heavy",
                q5_answerability,
                q5_answer,
                "scope_demo",
                q5_group,
                q5_rule,
                q5_gold_count,
                3,
                "moderate",
                "false",
                "draft",
                "Distractor-heavy query; review plausible competing evidence.",
            ])

            if q5_answerability == "conflict":
                qrels.append([
                    "controlled_tier_a_v0.3.1",
                    q5_id,
                    doc_id,
                    version,
                    f"{doc_id}_U02",
                    2,
                    units[1],
                    "true",
                    q5_group,
                    "",
                ])
                qrels.append([
                    "controlled_tier_a_v0.3.1",
                    q5_id,
                    doc_id,
                    version,
                    f"{doc_id}_U05",
                    2,
                    units[4],
                    "true",
                    q5_group,
                    "",
                ])
            elif q5_answerability == "answerable":
                qrels.append([
                    "controlled_tier_a_v0.3.1",
                    q5_id,
                    doc_id,
                    version,
                    f"{doc_id}_U05",
                    2,
                    units[4],
                    "false",
                    "",
                    "",
                ])

    # ---------------------------------------------------------
    # Write documents
    # ---------------------------------------------------------
    with (OUT / "documents.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f)
        writer.writerow([
            "dataset_id",
            "source_doc_id",
            "document_version",
            "source_unit_id",
            "unit_order",
            "content_hash_sha256",
            "source_type",
            "source_reference",
            "license",
            "text",
        ])
        writer.writerows(documents)

    # ---------------------------------------------------------
    # Write queries
    # ---------------------------------------------------------
    with (OUT / "queries.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f)
        writer.writerow([
            "dataset_id",
            "query_id",
            "primary_source_doc_id",
            "question",
            "question_type",
            "answerability",
            "gold_answer",
            "scope_id",
            "conflict_group_id",
            "resolution_rule",
            "gold_evidence_count",
            "distractor_unit_count",
            "lexical_overlap_bucket",
            "requires_multi_hop",
            "review_status",
            "annotation_notes",
        ])
        writer.writerows(queries)

    # ---------------------------------------------------------
    # Write qrels
    # ---------------------------------------------------------
    with (OUT / "qrels.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f)
        writer.writerow([
            "dataset_id",
            "query_id",
            "source_doc_id",
            "document_version",
            "source_unit_id",
            "relevance_grade",
            "gold_evidence_span",
            "conflicting_unit_flag",
            "conflict_group_id",
            "annotation_notes",
        ])
        writer.writerows(qrels)

    # ---------------------------------------------------------
    # File checksums
    # ---------------------------------------------------------
    checksum_rows = []

    for filename in [
        "documents.csv",
        "queries.csv",
        "qrels.csv",
    ]:
        path = OUT / filename
        digest = hashlib.sha256(path.read_bytes()).hexdigest()

        checksum_rows.append([
            filename,
            "SHA-256",
            digest,
        ])

    with (OUT / "SHA256SUMS.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f)
        writer.writerow([
            "file",
            "algorithm",
            "sha256",
        ])
        writer.writerows(checksum_rows)

    print("TIER A BUILD COMPLETE")
    print(f"documents={len(documents) // 6}")
    print(f"retrieval_units={len(documents)}")
    print(f"queries={len(queries)}")
    print(f"qrels={len(qrels)}")
    print(f"output={OUT}")


if __name__ == "__main__":
    main()
