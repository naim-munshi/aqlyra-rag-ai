import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = ROOT / "evaluation"
CORPUS_DIR = EVALUATION_DIR / "corpus"
DATASET_PATH = (
    EVALUATION_DIR
    / "retrieval_cases.json"
)


DOCUMENTS = (
    {
        "filename": "security_policy.md",
        "sections": (
            {
                "title": "Annual Review",
                "topic": "security governance",
                "fact": (
                    "The annual security review "
                    "happens every October."
                ),
                "query_id": "security-review-month",
                "query": (
                    "Which month is the yearly "
                    "security assessment scheduled?"
                ),
            },
            {
                "title": "Emergency Credentials",
                "topic": "privileged access",
                "fact": (
                    "The emergency credential "
                    "reference is ZX-41-LANTERN."
                ),
                "query_id": "security-emergency-code",
                "query": (
                    "What is the emergency "
                    "credential reference code?"
                ),
            },
        ),
    },
    {
        "filename": "operations_policy.md",
        "sections": (
            {
                "title": "Incident Retention",
                "topic": "incident operations",
                "fact": (
                    "Incident records are retained "
                    "for seven years."
                ),
                "query_id": "incident-retention",
                "query": (
                    "How long must incident "
                    "records be kept?"
                ),
            },
            {
                "title": "Severity One Response",
                "topic": "critical incident response",
                "fact": (
                    "A severity-one incident must "
                    "be acknowledged within "
                    "15 minutes."
                ),
                "query_id": "sev1-acknowledgement",
                "query": (
                    "What is the acknowledgement "
                    "deadline for a severity-one "
                    "incident?"
                ),
            },
        ),
    },
    {
        "filename": "platform_handbook.md",
        "sections": (
            {
                "title": "Vector Backup",
                "topic": "retrieval infrastructure",
                "fact": (
                    "The nightly vector backup "
                    "starts at 02:30 UTC."
                ),
                "query_id": "vector-backup-time",
                "query": (
                    "At what UTC time does the "
                    "nightly vector backup begin?"
                ),
            },
            {
                "title": "Retrieval Cache",
                "topic": "retrieval caching",
                "fact": (
                    "The retrieval cache has an "
                    "18-minute TTL."
                ),
                "query_id": "retrieval-cache-ttl",
                "query": (
                    "How long does a retrieval "
                    "cache entry remain valid?"
                ),
            },
        ),
    },
    {
        "filename": "research_notes.md",
        "sections": (
            {
                "title": "Orbit Experiment",
                "topic": "evaluation research",
                "fact": (
                    "Experiment ORBIT-73 used "
                    "1,200 samples."
                ),
                "query_id": "orbit-sample-count",
                "query": (
                    "How many samples were used "
                    "in experiment ORBIT-73?"
                ),
            },
            {
                "title": "Validation Split",
                "topic": "model evaluation",
                "fact": (
                    "The validation split was "
                    "18 percent of the dataset."
                ),
                "query_id": "validation-split",
                "query": (
                    "What fraction of the dataset "
                    "was reserved for validation?"
                ),
            },
        ),
    },
    {
        "filename": "support_manual.md",
        "sections": (
            {
                "title": "Priority One Escalation",
                "topic": "customer support",
                "fact": (
                    "A priority-one support case "
                    "is escalated after 12 minutes."
                ),
                "query_id": "p1-escalation",
                "query": (
                    "After how many minutes is a "
                    "priority-one support case "
                    "escalated?"
                ),
            },
            {
                "title": "Account Recovery",
                "topic": "identity recovery",
                "fact": (
                    "Account recovery requires "
                    "two independent identity "
                    "signals."
                ),
                "query_id": "recovery-signals",
                "query": (
                    "How many independent identity "
                    "signals are required for "
                    "account recovery?"
                ),
            },
        ),
    },
    {
        "filename": "privacy_standard.md",
        "sections": (
            {
                "title": "Data Export Requests",
                "topic": "privacy operations",
                "fact": (
                    "Approved data export requests "
                    "must be completed within "
                    "21 days."
                ),
                "query_id": "export-deadline",
                "query": (
                    "What is the completion "
                    "deadline for an approved "
                    "data export request?"
                ),
            },
            {
                "title": "Audit Log Retention",
                "topic": "privacy auditing",
                "fact": (
                    "Privacy audit logs are "
                    "retained for 400 days."
                ),
                "query_id": "audit-log-retention",
                "query": (
                    "For how many days are privacy "
                    "audit logs retained?"
                ),
            },
        ),
    },
    {
        "filename": "deployment_guide.md",
        "sections": (
            {
                "title": "Canary Release",
                "topic": "software deployment",
                "fact": (
                    "A production canary begins "
                    "with 5 percent of traffic."
                ),
                "query_id": "canary-traffic",
                "query": (
                    "What percentage of traffic "
                    "does a production canary "
                    "receive initially?"
                ),
            },
            {
                "title": "Rollback Threshold",
                "topic": "deployment reliability",
                "fact": (
                    "Rollback is triggered when "
                    "the error rate exceeds "
                    "2.5 percent for three "
                    "consecutive minutes."
                ),
                "query_id": "rollback-threshold",
                "query": (
                    "What error-rate condition "
                    "automatically triggers "
                    "rollback?"
                ),
            },
        ),
    },
    {
        "filename": "finance_controls.md",
        "sections": (
            {
                "title": "Invoice Approval",
                "topic": "financial controls",
                "fact": (
                    "Vendor invoices above "
                    "25,000 dollars require "
                    "two approvers."
                ),
                "query_id": "invoice-approval",
                "query": (
                    "How many approvers are needed "
                    "for a vendor invoice above "
                    "25,000 dollars?"
                ),
            },
            {
                "title": "Monthly Close",
                "topic": "financial reporting",
                "fact": (
                    "The monthly accounting close "
                    "locks on the fourth business "
                    "day."
                ),
                "query_id": "monthly-close-lock",
                "query": (
                    "On which business day does "
                    "the monthly accounting close "
                    "become locked?"
                ),
            },
        ),
    },
    {
        "filename": "data_governance.md",
        "sections": (
            {
                "title": "Dataset Registry",
                "topic": "data governance",
                "fact": (
                    "The restricted dataset "
                    "registry label is DV-88-PINE."
                ),
                "query_id": "dataset-registry-label",
                "query": (
                    "What is the registry label "
                    "for the restricted dataset?"
                ),
            },
            {
                "title": "Telemetry Retention",
                "topic": "data lifecycle",
                "fact": (
                    "Raw telemetry is deleted "
                    "after 45 days."
                ),
                "query_id": "telemetry-retention",
                "query": (
                    "When is raw telemetry "
                    "deleted?"
                ),
            },
        ),
    },
    {
        "filename": "continuity_plan.md",
        "sections": (
            {
                "title": "Recovery Objective",
                "topic": "business continuity",
                "fact": (
                    "The recovery time objective "
                    "is 90 minutes."
                ),
                "query_id": "recovery-time-objective",
                "query": (
                    "What is the documented "
                    "recovery time objective?"
                ),
            },
            {
                "title": "Failover Exercise",
                "topic": "disaster recovery",
                "fact": (
                    "The scheduled failover test "
                    "runs on the first Tuesday "
                    "of March and September."
                ),
                "query_id": "failover-schedule",
                "query": (
                    "When are the scheduled "
                    "failover tests performed?"
                ),
            },
        ),
    },
)


FILLER_TEMPLATES = (
    (
        "The {topic} process is documented so "
        "operators can apply the same procedure "
        "during routine work and formal reviews."
    ),
    (
        "Teams record decisions related to "
        "{topic} in the internal control log "
        "and review exceptions with the "
        "responsible owner."
    ),
    (
        "Monitoring for {topic} is performed "
        "through normal operational dashboards "
        "and significant deviations are "
        "investigated."
    ),
    (
        "The organization periodically checks "
        "{topic} controls to confirm that "
        "documentation and actual practice "
        "remain aligned."
    ),
    (
        "Changes affecting {topic} are reviewed "
        "before deployment and are recorded with "
        "enough context for later audit."
    ),
    (
        "Routine reporting for {topic} includes "
        "status, ownership, exceptions, and "
        "follow-up actions when required."
    ),
)


def build_section(
    *,
    title: str,
    topic: str,
    fact: str,
) -> str:
    paragraphs: list[str] = [
        f"## {title}",
        "",
    ]

    # Enough natural context to make each section
    # substantial and to create a non-trivial
    # multi-chunk document under IAHC-X.
    for cycle in range(3):
        for template in FILLER_TEMPLATES:
            sentence = template.format(
                topic=topic
            )

            paragraphs.append(sentence)

        if cycle == 1:
            paragraphs.append("")
            paragraphs.append(fact)
            paragraphs.append("")

    return "\n\n".join(
        paragraphs
    )


def build_document(
    document: dict,
) -> str:
    parts = [
        (
            "# Aqlyra Controlled Retrieval "
            "Evaluation Document"
        ),
        "",
        (
            "This synthetic document is part of "
            "the controlled Aqlyra retrieval "
            "benchmark corpus."
        ),
        "",
    ]

    for section in document["sections"]:
        parts.append(
            build_section(
                title=section["title"],
                topic=section["topic"],
                fact=section["fact"],
            )
        )

    return "\n\n".join(parts).strip() + "\n"


def main() -> None:
    CORPUS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cases: list[dict[str, str]] = []

    for document in DOCUMENTS:
        filename = document["filename"]

        content = build_document(
            document
        )

        (
            CORPUS_DIR
            / filename
        ).write_text(
            content,
            encoding="utf-8",
        )

        for section in document["sections"]:
            cases.append(
                {
                    "query_id": (
                        section["query_id"]
                    ),
                    "query": section["query"],
                    "document_filename": (
                        filename
                    ),
                    "evidence_marker": (
                        section["fact"]
                    ),
                }
            )

    payload = {
        "version": 1,
        "benchmark_type": (
            "controlled synthetic retrieval"
        ),
        "description": (
            "Controlled Aqlyra retrieval corpus "
            "with semantic paraphrases and exact "
            "identifier questions."
        ),
        "cases": cases,
    }

    DATASET_PATH.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Documents: {len(DOCUMENTS)}"
    )

    print(
        f"Cases: {len(cases)}"
    )

    print(
        f"Corpus: {CORPUS_DIR}"
    )

    print(
        f"Dataset: {DATASET_PATH}"
    )


if __name__ == "__main__":
    main()
