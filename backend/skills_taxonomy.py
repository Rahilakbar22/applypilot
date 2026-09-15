"""
A curated taxonomy of skills used for CV parsing and job matching.

This is intentionally a plain Python list rather than a database or external
service: it keeps ApplyPilot dependency-free and instantly usable offline.
Extend CATEGORIES to broaden coverage for your own use case.
"""

CATEGORIES = {
    "Programming Languages": [
        "python", "javascript", "typescript", "java", "c++", "c#", "go", "golang",
        "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "sql",
        "html", "css", "bash", "shell scripting", "perl", "objective-c", "dart",
    ],
    "Frameworks & Libraries": [
        "react", "react.js", "angular", "vue", "vue.js", "next.js", "nuxt.js",
        "django", "flask", "fastapi", "express", "express.js", "spring", "spring boot",
        "rails", "ruby on rails", ".net", "asp.net", "laravel", "node.js", "jquery",
        "redux", "graphql", "rest api", "restful apis", "tailwind css", "bootstrap",
        "pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy",
        "matplotlib", "opencv",
    ],
    "Cloud & DevOps": [
        "aws", "amazon web services", "azure", "gcp", "google cloud", "docker",
        "kubernetes", "terraform", "ansible", "jenkins", "ci/cd", "github actions",
        "gitlab ci", "linux", "nginx", "serverless", "cloudformation", "helm",
        "prometheus", "grafana", "microservices",
    ],
    "Data & Machine Learning": [
        "machine learning", "deep learning", "data analysis", "data science",
        "data engineering", "data visualization", "natural language processing", "nlp",
        "computer vision", "etl", "airflow", "spark", "apache spark", "hadoop",
        "big data", "statistics", "a/b testing", "power bi", "tableau", "excel",
        "looker", "dbt", "snowflake", "bigquery", "redshift", "mlops",
    ],
    "Databases": [
        "postgresql", "postgres", "mysql", "mongodb", "redis", "sqlite",
        "elasticsearch", "dynamodb", "cassandra", "oracle", "nosql", "firebase",
        "supabase",
    ],
    "Design": [
        "figma", "sketch", "adobe xd", "photoshop", "illustrator", "ui design",
        "ux design", "ui/ux", "wireframing", "prototyping", "user research",
        "design systems", "typography", "interaction design", "after effects",
        "premiere pro", "indesign",
    ],
    "Product & Project Management": [
        "product management", "project management", "agile", "scrum", "kanban",
        "jira", "confluence", "roadmapping", "stakeholder management",
        "product strategy", "user stories", "okrs", "prince2", "pmp", "trello",
        "asana", "notion",
    ],
    "Marketing & Sales": [
        "seo", "sem", "content marketing", "social media marketing", "email marketing",
        "google analytics", "google ads", "facebook ads", "hubspot", "salesforce",
        "crm", "copywriting", "brand strategy", "growth marketing", "market research",
        "lead generation", "affiliate marketing", "marketing automation",
    ],
    "Finance & Business": [
        "financial modeling", "financial analysis", "accounting", "budgeting",
        "forecasting", "bookkeeping", "quickbooks", "sap", "excel modeling",
        "valuation", "investment analysis", "risk management", "audit",
        "business development", "negotiation", "operations management",
    ],
    "Soft Skills": [
        "leadership", "communication", "teamwork", "problem solving",
        "critical thinking", "time management", "adaptability", "collaboration",
        "mentoring", "public speaking", "conflict resolution", "creativity",
        "attention to detail", "decision making", "customer service",
    ],
    "Certifications": [
        "aws certified", "pmp certified", "cissp", "comptia", "ceh", "cfa",
        "six sigma", "itil", "scrum master", "csm", "google certified",
        "azure certified", "cpa",
    ],
}

# Flat lookup: skill -> category, all lowercase for case-insensitive matching.
ALL_SKILLS = {
    skill: category
    for category, skills in CATEGORIES.items()
    for skill in skills
}

import re as _re


def find_skills_in_text(text_lower: str) -> set[str]:
    """Word-boundary skill detection shared by CV parsing and job matching.

    Plain substring matching (`"r" in text`) produces false positives for
    short tokens - "r" matches inside "our", "postgres" matches inside
    "postgresql". This anchors each skill to non-alphanumeric boundaries so
    "r" only matches the standalone language, not every word containing it.
    """
    found = set()
    for skill in ALL_SKILLS:
        pattern = _re.escape(skill)
        if _re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text_lower):
            found.add(skill)
    return found

# Weak, vague phrases that hurt resume impact when they open a bullet point.
WEAK_PHRASES = [
    "responsible for", "worked on", "helped with", "tasked with", "duties included",
    "in charge of", "participated in", "involved in", "assisted with", "helped to",
]

# Strong action verbs that ATS systems and recruiters favor at the start of a bullet.
STRONG_VERBS = [
    "led", "built", "designed", "launched", "architected", "optimized", "reduced",
    "increased", "improved", "automated", "drove", "delivered", "implemented",
    "spearheaded", "scaled", "streamlined", "negotiated", "mentored", "created",
    "developed", "managed", "generated", "cut", "grew", "accelerated", "pioneered",
    "transformed", "restructured", "shipped", "engineered",
]

EDUCATION_KEYWORDS = [
    "bachelor", "b.sc", "bsc", "b.a", "ba ", "master", "m.sc", "msc", "mba",
    "ph.d", "phd", "doctorate", "associate degree", "diploma", "b.tech", "btech",
    "m.tech", "mtech",
]

