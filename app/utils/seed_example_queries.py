import json
import logging
import asyncio
from app.services.embedding_service import EmbeddingService
from app.services.chroma_service import ChromaService

logger = logging.getLogger(__name__)

# Our finalized set of example queries
EXAMPLE_QUERIES = [
    {
        "id": "example_active_members_by_org",
        "natural_query": "How many active members does ACME Corporation have?",
        "generated_sql": """
SELECT COUNT(*) as active_member_count 
FROM eligibility.member m
JOIN eligibility.organization o ON m.organization_id = o.id
WHERE o.name ILIKE '%ACME%'
AND m.effective_range @> CURRENT_DATE
        """,
        "explanation": "This query counts active members belonging to organizations with 'ACME' in their name. A member is considered active when the current date falls within their effective_range.",
        "tables": ["member", "organization"],
        "business_concepts": ["active_status", "organization_filtering"],
        "query_type": "count_aggregate"
    },
    {
        "id": "example_all_active_members_org",
        "natural_query": "List all active members from Wayne Enterprises",
        "generated_sql": """
SELECT m.* 
FROM eligibility.member m
JOIN eligibility.organization o ON m.organization_id = o.id
WHERE o.name ILIKE '%Wayne%'
AND m.effective_range @> CURRENT_DATE
        """,
        "explanation": "This query retrieves all data for active members belonging to Wayne Enterprises. Active members are those where the current date is within their effective_range.",
        "tables": ["member", "organization"],
        "business_concepts": ["active_status", "organization_filtering"],
        "query_type": "retrieval"
    },
    {
        "id": "example_active_vs_inactive",
        "natural_query": "Compare the count of active versus inactive members",
        "generated_sql": """
SELECT 
    CASE WHEN m.effective_range @> CURRENT_DATE THEN 'Active' ELSE 'Inactive' END as status,
    COUNT(*) as member_count
FROM eligibility.member m
GROUP BY (m.effective_range @> CURRENT_DATE)
        """,
        "explanation": "This query compares the number of active and inactive members by grouping them based on whether the current date is within their effective_range.",
        "tables": ["member"],
        "business_concepts": ["active_status", "comparative_analysis"],
        "query_type": "comparative_count"
    },
    {
        "id": "example_overeligibility_check",
        "natural_query": "Is John Smith born on 1980-01-01 overeligible?",
        "generated_sql": """
SELECT COUNT(DISTINCT m.organization_id) > 1 as is_overeligible
FROM eligibility.member m
WHERE m.first_name = 'John'
AND m.last_name = 'Smith'
AND m.date_of_birth = '1980-01-01'
AND m.effective_range @> CURRENT_DATE
        """,
        "explanation": "This query checks if a specific person is overeligible by counting how many distinct organizations they have active membership in. If the count is greater than 1, they are considered overeligible.",
        "tables": ["member"],
        "business_concepts": ["overeligibility", "active_status"],
        "query_type": "boolean_check"
    },
    {
        "id": "example_list_overeligible",
        "natural_query": "List all overeligible members with their organizations",
        "generated_sql": """
SELECT 
    m.first_name, 
    m.last_name, 
    m.date_of_birth, 
    COUNT(DISTINCT m.organization_id) as org_count,
    array_agg(DISTINCT o.name) as organizations
FROM 
    eligibility.member m
JOIN
    eligibility.organization o ON m.organization_id = o.id
WHERE 
    m.effective_range @> CURRENT_DATE
GROUP BY 
    m.first_name, m.last_name, m.date_of_birth
HAVING 
    COUNT(DISTINCT m.organization_id) > 1
        """,
        "explanation": "This query finds all overeligible members (those active in multiple organizations) and lists their names, birth dates, the count of organizations, and the names of those organizations.",
        "tables": ["member", "organization"],
        "business_concepts": ["overeligibility", "active_status"],
        "query_type": "complex_aggregate"
    },
    {
        "id": "example_verified_members",
        "natural_query": "How many members have verified their eligibility at ACME Corp?",
        "generated_sql": """
SELECT COUNT(DISTINCT m.id) as verified_count
FROM eligibility.member m
JOIN eligibility.organization o ON m.organization_id = o.id
JOIN eligibility.member_verification mv ON m.id = mv.member_id
JOIN eligibility.verification v ON mv.verification_id = v.id
WHERE o.name ILIKE '%ACME%'
AND m.effective_range @> CURRENT_DATE
AND v.verified_at IS NOT NULL
AND (v.deactivated_at IS NULL OR v.deactivated_at > CURRENT_DATE)
        """,
        "explanation": "This query counts members who have active verifications at ACME Corp. It joins the member, organization, member_verification, and verification tables to find records where verification has been completed and remains active.",
        "tables": ["member", "organization", "member_verification", "verification"],
        "business_concepts": ["verification_status", "active_verification"],
        "query_type": "count_aggregate"
    },
    {
        "id": "example_verification_attempts",
        "natural_query": "Show the verification success rate by organization",
        "generated_sql": """
SELECT 
    o.name as organization_name,
    COUNT(va.id) as total_attempts,
    SUM(CASE WHEN va.successful_verification THEN 1 ELSE 0 END) as successful_attempts,
    ROUND(100.0 * SUM(CASE WHEN va.successful_verification THEN 1 ELSE 0 END) / COUNT(va.id), 2) as success_rate
FROM eligibility.verification_attempt va
JOIN eligibility.verification v ON va.verification_id = v.id
JOIN eligibility.organization o ON va.organization_id = o.id
GROUP BY o.id, o.name
ORDER BY success_rate DESC
        """,
        "explanation": "This query calculates the verification success rate for each organization by dividing the number of successful verification attempts by the total number of attempts, then multiplying by 100 to get a percentage.",
        "tables": ["verification_attempt", "verification", "organization"],
        "business_concepts": ["verification_success_rate", "organization_comparison"],
        "query_type": "analytical_percentage"
    },
    {
        "id": "example_member_by_dob_email",
        "natural_query": "Find a member with email john.doe@example.com and date of birth January 1, 1980",
        "generated_sql": """
SELECT * FROM eligibility.member m
WHERE m.email = 'john.doe@example.com'
AND m.date_of_birth = '1980-01-01'
AND m.effective_range @> CURRENT_DATE
        """,
        "explanation": "This query finds active members with the specified email address and date of birth. This pattern is often used as a primary verification method for identifying members.",
        "tables": ["member"],
        "business_concepts": ["member_identification", "active_status"],
        "query_type": "direct_lookup"
    },
    {
    "id": "example_emails_partial_org_match",
    "natural_query": "Find emails from Stark Industries",
    "generated_sql": """
SELECT email 
FROM eligibility.member m
JOIN eligibility.organization o ON m.organization_id = o.id
WHERE o.name ILIKE '%stark%'
    """,
    "explanation": "This query retrieves email addresses for members belonging to any organization with 'Stark' in the name. Note that we use just the key distinctive part of the organization name for broader matching.",
    "tables": ["member", "organization"],
    "business_concepts": ["organization_filtering", "partial_name_matching"],
    "query_type": "retrieval"
},
]


async def seed_example_queries():
    """Seed the example queries into Chroma."""
    try:
        embedding_service = EmbeddingService()
        chroma_service = ChromaService()

        # Create collection for examples
        collection = chroma_service.client.get_or_create_collection(
            name="query_examples",
            metadata={"hnsw:space": "cosine"}
        )

        # Prepare batch data
        ids = []
        embeddings = []
        metadatas = []
        documents = []

        for example in EXAMPLE_QUERIES:
            # Create text for embedding
            example_text = f"{example['natural_query']} {example.get('explanation', '')}"

            # Generate embedding
            embedding = await embedding_service.get_embedding(example_text)

            if embedding:
                ids.append(example["id"])
                embeddings.append(embedding)
                metadatas.append({
                    "natural_query": example["natural_query"],
                    "generated_sql": example["generated_sql"],
                    "explanation": example.get("explanation", ""),
                    "tables": json.dumps(example.get("tables", [])),
                    "business_concepts": json.dumps(example.get("business_concepts", [])),
                    "query_type": example.get("query_type", ""),
                    "is_example": True
                })
                documents.append(example_text)

        # Upsert into Chroma
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )

        logger.info(f"Seeded {len(ids)} example queries into Chroma")
        return True
    except Exception as e:
        logger.error(f"Error seeding example queries: {str(e)}")
        return False