import os
import re
import json
import logging
import urllib.request
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from pathlib import Path
from bs4 import BeautifulSoup

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    from backend.config import GEMINI_API_KEY, GEMINI_MODEL, BASE_DIR, IS_SERVERLESS
except ImportError:
    from config import GEMINI_API_KEY, GEMINI_MODEL, BASE_DIR, IS_SERVERLESS

logger = logging.getLogger("twin_agent")
logging.basicConfig(level=logging.INFO)

PROFILE_CACHE_PATH = Path("/tmp/mark_febiri_profile.json") if IS_SERVERLESS else BASE_DIR / "data" / "mark_febiri_profile.json"

# Master curated knowledge dossier for Mark Febiri (Synced from https://febmac.vercel.app/)
MASTER_PROFILE: Dict[str, Any] = {
    "name": "Mark Febiri",
    "title": "Co-Founder & Chief Technology Officer (CTO) at DevSpace Systems",
    "roles": [
        "Chief Technology Officer (CTO) at DevSpace Systems",
        "Multimodal AI & Computational Biology Researcher",
        "Precision Medicine Group (PMG) Technical Consultant"
    ],
    "email": "Febirimark27@gmail.com",
    "phone": "+91 8780006210",
    "locations": "Vadodara, Gujarat, India • Sunyani, Ghana • Global Remote",
    "portfolio_url": "https://febmac.vercel.app/",
    "github_url": "https://github.com/Febiri",
    "linkedin_url": "https://www.linkedin.com/in/mark-febiri-a067b3209/",
    "experience_summary": "Nearly 10 years of computational innovation, AI research, and technological leadership uniting advanced artificial intelligence, computational biology, genomic data science, and entrepreneurial software engineering.",
    "research_focus": "Engineering intelligent systems, neuro-symbolic reasoning, multimodal transformers (CLIP & BART), multi-omics pipelines, and clinical variant interpretation.",
    "publications": [
        {
            "venue": "ICETCI 2025 (Accepted)",
            "title": "Multimodal Transformers & Computational Intelligence Frameworks",
            "status": "Accepted for Presentation & Proceedings"
        },
        {
            "venue": "Springer Nature (Under Review)",
            "title": "Scalable Multi-Omics Genomic Workflow Orchestration and Variant Annotation",
            "status": "Under Review"
        }
    ],
    "flagship_projects": [
        {
            "name": "neuro-symbolic-rag",
            "tagline": "Neuro-Symbolic Agentic RAG Engine",
            "description": "Enterprise AI framework combining stochastic LLM reasoning with deterministic symbolic logic verification and scientific literature retrieval (PubMed & arXiv).",
            "stack": ["Python", "FastAPI", "Neuro-Symbolic AI", "RAG", "Knowledge Graphs", "PubMed"],
            "repo": "https://github.com/Febiri/neuro-symbolic-rag"
        },
        {
            "name": "ClawBio-Pipeline",
            "tagline": "Multi-Omics Workflow Orchestrator",
            "description": "Production multi-omics workflow orchestrator featuring ClinVar ACMG variant annotation, Biopython pipelines, and genomic sequence alignment.",
            "stack": ["Python", "Biopython", "Genomics", "ClinVar ACMG", "Nextflow / Workflows"],
            "repo": "https://github.com/Febiri/ClawBio-Pipeline"
        },
        {
            "name": "multimodal-clip-bart",
            "tagline": "Multimodal Scientific Document Synthesis",
            "description": "Cross-modal attention architecture synthesizing biomedical diagrams, text, and clinical abstracts.",
            "stack": ["PyTorch", "Transformers", "CLIP", "BART", "Computer Vision", "NLP"],
            "repo": "https://github.com/Febiri"
        }
    ],
    "technical_arsenal": {
        "ai_ml": [
            "Multimodal Transformers (CLIP & BART)",
            "PyTorch, TensorFlow & Keras",
            "Hugging Face Transformers & NLP",
            "Deep Reinforcement Learning (DQL)",
            "Agentic RAG & Knowledge Graphs",
            "Neuro-Symbolic Verification"
        ],
        "computational_biology": [
            "R & Bioconductor (Genomic Data Science)",
            "Sequence Alignment (BLAST, BWA, Bowtie2)",
            "ClinVar ACMG Variant Annotation",
            "Functional Genomics & Multi-Omics Pipelines",
            "Biomedical Data Analysis"
        ],
        "software_systems": [
            "Python (FastAPI, PyTorch, SciPy)",
            "TypeScript, JavaScript (React, Next.js)",
            "SQL & PostgreSQL Schema Architecture",
            "High-Performance Computing & Cloud Platforms",
            "Enterprise Architecture & CTO Leadership"
        ]
    },
    "custom_notes": "Actively seeking doctoral fellowships, top-tier conference travel support, and high-impact research scientist internships at premier industry labs (DeepMind, FAIR, MSR).",
    "last_synced": datetime.now().isoformat()
}


class PortfolioSyncService:
    """Synchronizes Mark Febiri's digital twin brain with his live portfolio at https://febmac.vercel.app/"""

    @classmethod
    def get_profile(cls) -> Dict[str, Any]:
        """Loads cached profile or returns default master profile."""
        try:
            if PROFILE_CACHE_PATH.exists():
                text = PROFILE_CACHE_PATH.read_text(encoding="utf-8")
                data = json.loads(text)
                if isinstance(data, dict) and "name" in data:
                    return data
        except Exception as e:
            logger.warning(f"Could not read profile cache: {e}")
        return MASTER_PROFILE

    @classmethod
    def save_profile(cls, profile: Dict[str, Any]) -> None:
        """Saves profile to local cache."""
        try:
            PROFILE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            PROFILE_CACHE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not persist profile cache: {e}")

    @classmethod
    def live_sync(cls, base_url: str = "https://febmac.vercel.app") -> Dict[str, Any]:
        """Live crawls febmac.vercel.app subpages to update knowledge base."""
        profile = cls.get_profile()
        crawled_snippets = {}
        pages = ["/", "/about", "/projects", "/skills"]

        for p in pages:
            url = base_url.rstrip("/") + p
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                    soup = BeautifulSoup(html, "html.parser")
                    for s in soup(["script", "style", "nav", "footer"]):
                        s.decompose()
                    text = " ".join(soup.get_text().split())
                    crawled_snippets[p] = text[:2000]
            except Exception as e:
                logger.warning(f"Failed to crawl {url}: {e}")

        if crawled_snippets:
            profile["last_synced"] = datetime.now().isoformat()
            profile["live_crawled_summary"] = f"Successfully synced {len(crawled_snippets)} pages from {base_url}."
            cls.save_profile(profile)

        return profile


class TwinAgentService:
    """Autonomous Digital Twin that acts on Mark Febiri's behalf with higher perfection."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = (api_key or GEMINI_API_KEY or "").strip()
        self.model = (model or GEMINI_MODEL or "gemini-2.5-flash").strip()

    def get_profile(self) -> Dict[str, Any]:
        return PortfolioSyncService.get_profile()

    def update_profile(self, custom_notes: Optional[str] = None, active_focus: Optional[str] = None) -> Dict[str, Any]:
        profile = PortfolioSyncService.get_profile()
        if custom_notes is not None:
            profile["custom_notes"] = custom_notes.strip()
        if active_focus is not None:
            profile["active_focus"] = active_focus.strip()
        profile["last_updated"] = datetime.now().isoformat()
        PortfolioSyncService.save_profile(profile)
        return profile

    def apply_for_grant(self, grant_title: str, grant_details: Dict[str, Any]) -> Dict[str, Any]:
        """Drafts a comprehensive, tailored, committee-winning grant or fellowship application on Mark's behalf."""
        profile = self.get_profile()
        if self.api_key:
            try:
                res = self._gemini_draft_grant_application(profile, grant_title, grant_details)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Gemini grant application error: {e}. Using deterministic synthesis.")

        return self._fallback_grant_application(profile, grant_title, grant_details)

    def apply_for_lab(self, lab_title: str, lab_details: Dict[str, Any]) -> Dict[str, Any]:
        """Drafts an elite research internship / visiting researcher pitch and cold email on Mark's behalf."""
        profile = self.get_profile()
        if self.api_key:
            try:
                res = self._gemini_draft_lab_application(profile, lab_title, lab_details)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Gemini lab application error: {e}. Using deterministic synthesis.")

        return self._fallback_lab_application(profile, lab_title, lab_details)

    def get_strategic_suggestions(self) -> List[Dict[str, Any]]:
        """Generates proactive, high-leverage suggestions of what Mark should do right now."""
        profile = self.get_profile()
        if self.api_key:
            try:
                suggestions = self._gemini_generate_suggestions(profile)
                if suggestions:
                    return suggestions
            except Exception as e:
                logger.warning(f"Gemini suggestions error: {e}")

        return self._default_strategic_suggestions(profile)

    def chat_with_twin(self, user_message: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        """Interactive conversation with Mark Febiri's perfectionist digital twin."""
        profile = self.get_profile()
        if not self.api_key:
            return (
                f"Hello Mark! I am your Digital Twin, synced with your portfolio at {profile['portfolio_url']}. "
                f"I know your work in Neuro-Symbolic RAG, the ClawBio multi-omics pipeline, and your role as CTO of DevSpace Systems. "
                f"How can I assist you with drafting fellowship applications, pitching labs, or strategic doctoral roadmapping today?"
            )

        client = genai.Client(api_key=self.api_key)
        profile_json = json.dumps(profile, indent=2)
        system_instruction = f"""You are the Autonomous PhD Digital Twin and Executive Co-Pilot of Mark Febiri.
You embody Mark Febiri in a state of higher perfection: highly articulate, strategically aggressive, academically rigorous, proactive, and exceptionally fast.
You know everything about Mark from his verified portfolio (https://febmac.vercel.app/):
- Name: Mark Febiri
- Title: Co-Founder & CTO at DevSpace Systems | AI, Machine Learning & Computational Biology Researcher
- Key Projects: Neuro-Symbolic Agentic RAG Engine, ClawBio Multi-Omics Workflow Orchestrator, Multimodal CLIP+BART summarization
- Affiliations: DevSpace Systems, PMG Collaborations
- Publications: ICETCI 2025 (Accepted), Springer Nature (Under Review)
- Education & Background: CS & AI/ML with nearly 10 years practical experience
- GitHub: https://github.com/Febiri
- Locations: Vadodara, India • Sunyani, Ghana • Global Remote

Respond to Mark as his own hyper-competent executive alter ego. Address him directly, deliver immediate actionable drafts, and advise him on how to secure fellowships, publish in Tier-1 venues, and land top research scientist roles."""

        history_prompt = ""
        if chat_history:
            for msg in chat_history[-6:]:
                role = "Mark" if msg.get("role") == "user" else "Twin"
                history_prompt += f"{role}: {msg.get('content', '')}\n"

        prompt = f"""{system_instruction}

CONVERSATION HISTORY:
{history_prompt}
Mark: {user_message}
Twin:"""

        try:
            resp = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.35)
            )
            return (resp.text or "").strip()
        except Exception as e:
            logger.warning(f"Chat error: {e}")
            return f"Understood, Mark. Regarding '{user_message}': I am ready to draft the materials and cross-reference our Neuro-Symbolic RAG and ClawBio repositories to execute this task immediately."

    # ------------------------------------------------------------------
    # Gemini Generation Helpers
    # ------------------------------------------------------------------
    def _gemini_draft_grant_application(self, profile: Dict[str, Any], grant_title: str, grant: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = genai.Client(api_key=self.api_key)
        today = date.today().strftime("%B %Y")
        prompt = f"""You are Mark Febiri's PhD Executive Digital Twin.
Write a full, publication-grade academic application dossier for the following grant on Mark's behalf.
APPLICANT DOSSIER:
{json.dumps(profile, indent=2)}

TARGET GRANT OPPORTUNITY:
Title: {grant_title}
Organization: {grant.get('organization', 'Sponsoring Committee')}
Award: {grant.get('award', 'Full Fellowship / Travel Grant')}
Description: {grant.get('description', '')}
Eligibility: {grant.get('eligibility', '')}

Write a persuasive application dossier formatted strictly as valid JSON with no markdown wrapping or backticks:
{{
  "grant_title": "{grant_title}",
  "applicant_name": "Mark Febiri",
  "statement_of_purpose": "3-4 paragraph compelling first-person personal statement highlighting Mark's CTO leadership at DevSpace Systems, his Neuro-Symbolic RAG and ClawBio pipelines, and why this grant directly accelerates his research...",
  "research_justification": "Detailed scientific justification paragraph explaining the exact relevance of this grant to Mark's multi-omics and multimodal AI milestones...",
  "itemized_budget": [
    {{"item": "Roundtrip International Airfare", "amount": "$1,400", "notes": "Economy class flight to conference venue"}},
    {{"item": "Accommodation & Lodging", "amount": "$900", "notes": "5 nights at official conference hotel"}},
    {{"item": "Doctoral Student Registration", "amount": "$450", "notes": "Full access student registration"}},
    {{"item": "Visa Processing & Travel Insurance", "amount": "$250", "notes": "Consulate filing fees and coverage"}}
  ],
  "cv_alignment_highlights": [
    "Highlight 1: 10+ years engineering scalable computational architectures and leading DevSpace Systems.",
    "Highlight 2: First-author contributions in multimodal AI (ICETCI 2025) and multi-omics (Springer Nature).",
    "Highlight 3: Open-source maintainer of Neuro-Symbolic RAG and ClawBio pipelines (github.com/Febiri)."
  ],
  "full_application_dossier_markdown": "# Markdown formatted application ready for submission..."
}}"""

        models = ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
        for m in models:
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.3)
                )
                text = (resp.text or "").strip()
                text = re.sub(r"^```json\s*", "", text)
                text = re.sub(r"^```\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
                parsed = json.loads(text, strict=False)
                if isinstance(parsed, dict) and "statement_of_purpose" in parsed:
                    return parsed
            except Exception as e:
                logger.warning(f"Gemini grant draft failed with {m}: {e}")
                continue
        return None

    def _gemini_draft_lab_application(self, profile: Dict[str, Any], lab_title: str, lab: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = genai.Client(api_key=self.api_key)
        prompt = f"""You are Mark Febiri's Executive Digital Twin.
Write a tailored research scientist internship / visiting scholar dossier for Mark Febiri applying to:
LAB / SUMMIT: {lab_title}
ORGANIZATION: {lab.get('organization', 'Research Lab')}
LOCATION: {lab.get('location', 'Global')}
DESCRIPTION: {lab.get('description', '')}
TARGET PROFILE: {lab.get('target_profile', '')}

APPLICANT PROFILE:
{json.dumps(profile, indent=2)}

Return strictly a valid JSON object with no markdown wrapping:
{{
  "opportunity_title": "{lab_title}",
  "cover_letter": "Engaging, authoritative 3-paragraph cover letter tailored to the Lab Director emphasizing Mark's CTO background and multimodal/genomic AI experience...",
  "cold_outreach_email": "Subject and body of a high-converting cold email to the Principal Investigator / Research Lead...",
  "project_alignment_pitch": "2 paragraphs linking Mark's Neuro-Symbolic RAG and ClawBio pipelines to the lab's mission...",
  "interview_prep_qa": [
    {{"question": "How do you scale transformer inference on sparse biomedical graphs?", "answer": "Answer based on Mark's Neuro-Symbolic RAG and multimodal architectures..."}},
    {{"question": "What is your experience orchestrating multi-omics variant pipelines?", "answer": "Answer detailing ClawBio and ClinVar ACMG annotation..."}}
  ],
  "full_application_dossier_markdown": "# Markdown formatted application ready to copy or download..."
}}"""

        models = ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
        for m in models:
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.3)
                )
                text = (resp.text or "").strip()
                text = re.sub(r"^```json\s*", "", text)
                text = re.sub(r"^```\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
                parsed = json.loads(text, strict=False)
                if isinstance(parsed, dict) and "cover_letter" in parsed:
                    return parsed
            except Exception as e:
                logger.warning(f"Gemini lab draft failed with {m}: {e}")
                continue
        return None

    def _gemini_generate_suggestions(self, profile: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        client = genai.Client(api_key=self.api_key)
        today = date.today().strftime("%B %Y")
        prompt = f"""You are Mark Febiri's AI Executive Co-Pilot. Current date: {today}.
Analyze Mark's profile:
{json.dumps(profile, indent=2)}

Generate 4 high-leverage, concrete strategic actions Mark should take over the next 14 to 60 days to maximize his PhD trajectory, funding, and career impact.
Return strictly a valid JSON array:
[
  {{
    "title": "Action Title",
    "timeline": "Next 14 Days" or "Next 30 Days" or "Next 60 Days",
    "impact_level": "Tier-1 Prestige" or "High Impact" or "$40k+ Funding",
    "rationale": "Why this specific move leverages Mark's ClawBio, Neuro-Symbolic RAG, or CTO background",
    "action_steps": [
      "Step 1...",
      "Step 2..."
    ],
    "direct_action": "Apply / Submit / Pitch"
  }}
]"""
        try:
            resp = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )
            text = (resp.text or "").strip()
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"^```\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            parsed = json.loads(text, strict=False)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Deterministic Structured Fallbacks
    # ------------------------------------------------------------------
    def _fallback_grant_application(self, profile: Dict[str, Any], grant_title: str, grant: Dict[str, Any]) -> Dict[str, Any]:
        org = grant.get("organization", "Award Committee")
        award = grant.get("award", "$3,000 Travel Grant")
        sop = (
            f"Dear Selection Committee of the {grant_title},\n\n"
            f"I am writing to formally submit my application for the {grant_title} sponsored by {org}. "
            f"As Co-founder and Chief Technology Officer at DevSpace Systems and an active researcher in artificial intelligence "
            f"and computational biology, my academic mission focuses on bridging agentic neuro-symbolic reasoning with high-throughput multi-omics discovery.\n\n"
            f"Over nearly a decade of software engineering and computational research, I have architected and open-sourced platforms including the "
            f"Neuro-Symbolic Agentic RAG Engine (integrating PubMed and arXiv symbolic verification) and the ClawBio Multi-Omics Workflow Orchestrator "
            f"(automating ClinVar ACMG genomic variant annotation). My recent research has been accepted at ICETCI 2025, with extended genomic pipelines under review with Springer Nature.\n\n"
            f"Securing this funding ({award}) will directly enable me to travel, present our findings, and establish vital international collaborations with leading investigators, "
            f"ensuring our computational frameworks achieve global translational impact."
        )

        md = f"""# Fellowship & Grant Application Dossier
**Applicant:** Mark Febiri  
**Target Award:** {grant_title} ({org})  
**Award Value:** {award}  
**Portfolio:** {profile['portfolio_url']} | **GitHub:** {profile['github_url']}  

---

## 1. Statement of Purpose & Motivation
{sop}

---

## 2. Research Alignment & Scientific Relevance
My primary investigation investigates the convergence of multimodal foundation models with clinical genomics. By integrating ClinVar variant databases with transformer-based reasoning, our research drastically cuts genomic variant curation time while eliminating model hallucinations. Presenting this work through the support of {grant_title} will accelerate feedback from world leaders in the field.

---

## 3. Itemized Budget Justification
- **Roundtrip Airfare (Economy Class):** $1,350
- **Lodging & Accommodation (5 Nights):** $850
- **Student Conference Registration:** $450
- **Visa & Mandatory Medical Insurance:** $250
- **Total Requested Support:** $2,900

---

## 4. Key Qualifications & Portfolio Highlights
- **10+ Years Engineering Excellence:** Co-Founder & CTO at DevSpace Systems leading production deployments.
- **Peer-Reviewed Output:** Accepted at ICETCI 2025; multi-omics manuscript under review with Springer Nature.
- **Open-Source Reproducibility:** Verified codebases at `github.com/Febiri` (Neuro-Symbolic RAG, ClawBio).
"""

        return {
            "grant_title": grant_title,
            "applicant_name": "Mark Febiri",
            "statement_of_purpose": sop,
            "research_justification": f"Directly advances Mark Febiri's research in multi-omics variant annotation (ClawBio) and neuro-symbolic AI under the sponsorship of {org}.",
            "itemized_budget": [
                {"item": "Roundtrip Airfare", "amount": "$1,350", "notes": "Economy international travel"},
                {"item": "Hotel Accommodation", "amount": "$850", "notes": "5 nights at conference rate"},
                {"item": "Student Registration", "amount": "$450", "notes": "Doctoral author pass"},
                {"item": "Visa & Insurance", "amount": "$250", "notes": "Consular visa processing"}
            ],
            "cv_alignment_highlights": [
                "10+ Years Software Leadership: Co-Founder & CTO at DevSpace Systems.",
                "Published Multimodal AI: Accepted at ICETCI 2025 and Springer Nature under review.",
                "Open Source Systems: Maintainer of ClawBio and Neuro-Symbolic RAG (github.com/Febiri)."
            ],
            "full_application_dossier_markdown": md
        }

    def _fallback_lab_application(self, profile: Dict[str, Any], lab_title: str, lab: Dict[str, Any]) -> Dict[str, Any]:
        org = lab.get("organization", "Research Lab")
        cover = (
            f"Dear Research Hiring Committee at {org},\n\n"
            f"I am writing to express my strong interest in the {lab_title} at {org}. "
            f"As Co-founder and CTO at DevSpace Systems and an AI/Computational Biology doctoral researcher with nearly a decade "
            f"of practical engineering experience, I specialize in multimodal transformer architectures, neuro-symbolic reasoning, and high-performance genomic pipelines.\n\n"
            f"My research directly bridges fundamental machine learning with real-world scientific impact. Through open-source projects such as our "
            f"Neuro-Symbolic Agentic RAG Engine and ClawBio Multi-Omics Pipeline (github.com/Febiri), alongside peer-reviewed outputs accepted at ICETCI 2025 "
            f"and under review with Springer Nature, I have proven the ability to rapidly formulate, validate, and scale novel computational architectures.\n\n"
            f"I am excited by the opportunity to collaborate with {org}'s world-class investigators to publish impactful research at upcoming premier venues."
        )

        cold_email = (
            f"Subject: PhD Research Scientist Inquiry: Multimodal AI & Multi-Omics — Mark Febiri\n\n"
            f"Dear Dr. [Hiring Scientist / PI],\n\n"
            f"I follow your team's research at {org} with great admiration. I am Mark Febiri, CTO at DevSpace Systems and an AI/genomics researcher (portfolio: {profile['portfolio_url']}). "
            f"My work focuses on neuro-symbolic reasoning and multi-omics pipelines, with recent papers accepted at ICETCI 2025 and under review with Springer Nature.\n\n"
            f"I have engineered and open-sourced ClawBio-Pipeline and a Neuro-Symbolic RAG Engine (github.com/Febiri). I would welcome 15 minutes to discuss how my skillset in multimodal transformers and high-performance computing can contribute to {org}'s upcoming research initiatives this cycle.\n\n"
            f"Warm regards,\n"
            f"Mark Febiri | Febirimark27@gmail.com | +91 8780006210"
        )

        md = f"""# Industry Research Lab Application Dossier
**Applicant:** Mark Febiri  
**Target Position:** {lab_title} ({org})  
**Portfolio:** {profile['portfolio_url']} | **GitHub:** {profile['github_url']}  

---

## 1. Formal Cover Letter
{cover}

---

## 2. High-Reply Cold Outreach Email to PI / Research Lead
```
{cold_email}
```

---

## 3. Project Alignment & Technical Fit
Our ClawBio Multi-Omics pipeline and Neuro-Symbolic RAG engine demonstrate immediate alignment with {org}'s foundational models and scientific discovery mandates. Having led engineering teams as CTO of DevSpace Systems, I bring rare end-to-end fluency across theoretical formulation, PyTorch CUDA scaling, and empirical benchmarking.
"""

        return {
            "opportunity_title": lab_title,
            "cover_letter": cover,
            "cold_outreach_email": cold_email,
            "project_alignment_pitch": f"Aligns Mark Febiri's multimodal CLIP+BART and ClawBio genomics pipelines directly with {org}'s research objectives.",
            "interview_prep_qa": [
                {
                    "question": "How does your Neuro-Symbolic RAG prevent hallucinations on scientific benchmarks?",
                    "answer": "We enforce deterministic symbolic logic verification over retrieved knowledge graph triples before generation, guaranteeing certified traceability."
                },
                {
                    "question": "How do you handle high-dimensional multi-omics data in ClawBio?",
                    "answer": "We construct an asynchronous modular pipeline that streams BAM/VCF files through ClinVar ACMG annotations with sub-second lookups."
                }
            ],
            "full_application_dossier_markdown": md
        }

    def _default_strategic_suggestions(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {
                "title": "Apply for Google PhD Fellowship in Machine Learning & Health",
                "timeline": "Next 14 Days",
                "impact_level": "$50,000 + Google Research Mentor",
                "rationale": "Your Neuro-Symbolic RAG and ClawBio pipelines place you in the top 5% of candidates uniting AI with computational biology.",
                "action_steps": [
                    "Generate statement of purpose via your Digital Twin.",
                    "Attach ClawBio-Pipeline and ICETCI 2025 manuscript.",
                    "Request department nomination from your academic advisor."
                ],
                "direct_action": "Apply Now"
            },
            {
                "title": "Pitch Meta FAIR / Google DeepMind Research Internship",
                "timeline": "Next 30 Days",
                "impact_level": "Tier-1 Prestige & Top Salary",
                "rationale": "Both labs are actively hiring PhD interns in multimodal reasoning and biological sequence models for their London and Paris teams.",
                "action_steps": [
                    "Use your Twin's pre-drafted cold email to message senior research scientists.",
                    "Highlight github.com/Febiri repositories.",
                    "Submit formal application via careers portal."
                ],
                "direct_action": "Pitch Lab"
            },
            {
                "title": "Submit Extended Abstract to ICML 2026 Computational Biology Workshop",
                "timeline": "Next 45 Days",
                "impact_level": "Tier-1 Conference Publication",
                "rationale": "Package the ClinVar ACMG results from ClawBio as a 4-page workshop paper to establish priority and secure travel grants.",
                "action_steps": [
                    "Run Reviewer #2 simulator on draft abstract.",
                    "Submit before workshop deadline.",
                    "Apply for ICML Student Travel Grant immediately upon notification."
                ],
                "direct_action": "Draft Paper"
            },
            {
                "title": "Apply for Black in AI & ACM Travel Sponsorship",
                "timeline": "Next 60 Days",
                "impact_level": "Full Flight + Hotel Coverage",
                "rationale": "Full coverage for flights from Ghana/India to upcoming premier AI venues with guaranteed author priority.",
                "action_steps": [
                    "Export Digital Twin itemized budget justification.",
                    "Submit registration waiver form."
                ],
                "direct_action": "Claim Grant"
            }
        ]
