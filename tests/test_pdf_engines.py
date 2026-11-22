import sys
import os
sys.path.insert(0, os.path.abspath("."))
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_all():
    print("1. Testing HTML routes...")
    routes = ['/', '/conferences', '/app', '/radar', '/reviewer', '/grants', '/lab-connector', '/agent', '/twin', '/copilot']
    for r in routes:
        resp = client.get(r)
        assert resp.status_code == 200, f"Route {r} failed with status {resp.status_code}"
        print(f"  [PASS] {r} -> {resp.status_code} ({len(resp.text)} bytes)")

    print("\n2. Testing /api/reviewer/simulate...")
    resp = client.post('/api/reviewer/simulate', json={
        'title': 'Test Paper on Efficient Attention',
        'abstract': 'We introduce a low rank attention mechanism for transformers.',
        'target_venue': 'NeurIPS / IEEE'
    })
    assert resp.status_code == 200, f"/api/reviewer/simulate failed: {resp.text}"
    data = resp.json()
    assert 'overall_score' in data, 'Missing overall_score'
    assert 'copy_paste_suggestions' in data, 'Missing copy_paste_suggestions'
    assert 'revised_document_draft' in data, 'Missing revised_document_draft'
    print(f"  [PASS] /api/reviewer/simulate returned score {data['overall_score']}, suggestions and draft present.")

    print("\n3. Testing /api/radar/analyze...")
    resp = client.post('/api/radar/analyze', json={
        'topic': 'Graph Neural Network Compression',
        'idea_proposal': 'Quantizing GNN weight tensors using Hessian information'
    })
    assert resp.status_code == 200, f"/api/radar/analyze failed: {resp.text}"
    data = resp.json()
    assert 'novelty_score' in data, 'Missing novelty_score'
    print(f"  [PASS] /api/radar/analyze returned novelty score: {data['novelty_score']}%")

    print("\n4. Testing /api/reviewer/upload-pdf...")
    pdf_path = 'static/pdfs/upload_7597e5a8_MMSum_reviewer_reply_4.pdf'
    with open(pdf_path, 'rb') as f:
        resp = client.post(
            '/api/reviewer/upload-pdf',
            files={'file': ('test_paper.pdf', f, 'application/pdf')},
            data={'target_venue': 'NeurIPS / IEEE'}
        )
    assert resp.status_code == 200, f"/api/reviewer/upload-pdf failed: {resp.text}"
    data = resp.json()
    assert data.get('success') is True, 'Success is not True'
    assert 'review' in data, 'Missing review'
    assert 'copy_paste_suggestions' in data['review'], 'Missing copy_paste_suggestions in review'
    assert 'revised_document_draft' in data['review'], 'Missing revised_document_draft in review'
    print(f"  [PASS] /api/reviewer/upload-pdf extracted {data['word_count']} words across {data['total_pages']} pages, verdict: {data['review']['verdict']}")
    print(f"  [PASS] Copy-paste suggestions: abstract len={len(data['review']['copy_paste_suggestions']['revised_abstract'])}, contribs={len(data['review']['copy_paste_suggestions']['strengthened_contributions'])}")

    print("\n5. Testing /api/radar/upload-pdf...")
    with open(pdf_path, 'rb') as f:
        resp = client.post(
            '/api/radar/upload-pdf',
            files={'file': ('test_paper.pdf', f, 'application/pdf')},
            data={'target_domain': 'Computer Science'}
        )
    assert resp.status_code == 200, f"/api/radar/upload-pdf failed: {resp.text}"
    data = resp.json()
    assert data.get('success') is True, 'Success is not True'
    assert 'radar' in data, 'Missing radar'
    assert 'novelty_score' in data['radar'], 'Missing novelty_score in radar'
    print(f"  [PASS] /api/radar/upload-pdf extracted {data['word_count']} words, novelty: {data['radar']['novelty_score']}%, title: {data['radar'].get('extracted_title')}")

    print("\n6. Testing /api/grants/search with research work & destination...")
    resp = client.post('/api/grants/search', json={
        'research_work': 'Edge AI & Deep Learning',
        'destination': 'United States & Canada',
        'category': 'All'
    })
    assert resp.status_code == 200, f"Grants failed: {resp.text}"
    grants = resp.json()
    assert len(grants) > 0, "No grants returned"
    print(f"  [PASS] /api/grants/search returned {len(grants)} grants matched by topic & destination.")

    print("\n7. Testing /api/labs/search with research work & location...")
    resp = client.post('/api/labs/search', json={
        'research_work': 'Large Language Models',
        'location': 'United Kingdom & Europe',
        'item_type': 'All'
    })
    assert resp.status_code == 200, f"Labs failed: {resp.text}"
    labs = resp.json()
    assert len(labs) > 0, "No labs returned"
    print(f"  [PASS] /api/labs/search returned {len(labs)} labs matched by topic & location.")

    print("\n8. Testing Engine 07: Digital Twin & Executive Co-Pilot APIs...")
    # Profile check
    resp = client.get('/api/twin/profile')
    assert resp.status_code == 200, f"/api/twin/profile failed: {resp.text}"
    profile_data = resp.json()
    assert profile_data.get('name') == 'Mark Febiri', f"Unexpected name: {profile_data}"
    print(f"  [PASS] /api/twin/profile verified: {profile_data['name']} ({profile_data['title']})")

    # Strategic suggestions check
    resp = client.get('/api/twin/suggestions')
    assert resp.status_code == 200, f"/api/twin/suggestions failed: {resp.text}"
    sug_data = resp.json()
    assert isinstance(sug_data, list) and len(sug_data) > 0, f"Expected non-empty list of suggestions, got: {type(sug_data)}"
    print(f"  [PASS] /api/twin/suggestions returned {len(sug_data)} strategic roadmaps")

    # Apply on behalf of Mark for grant
    resp = client.post('/api/twin/apply-grant', json={
        'grant_title': 'NSF Graduate Research Fellowship Program (GRFP)',
        'grant_details': {
            'target_destination': 'United States',
            'focus_alignment': 'Neuro-Symbolic AI & Computational Biology'
        }
    })
    assert resp.status_code == 200, f"/api/twin/apply-grant failed: {resp.text}"
    grant_app = resp.json()
    assert grant_app.get('applicant_name') == 'Mark Febiri', f"Applicant name mismatch: {grant_app}"
    assert len(grant_app.get('statement_of_purpose', '')) > 200, "SOP too short"
    assert 'itemized_budget' in grant_app or 'budget_justification' in grant_app, "Missing budget info"
    print(f"  [PASS] /api/twin/apply-grant generated {len(grant_app['statement_of_purpose'])} chars SOP & budget items")

    # Apply on behalf of Mark for lab internship / residency
    resp = client.post('/api/twin/apply-lab', json={
        'lab_title': 'Google DeepMind Research Residency',
        'lab_details': {
            'location': 'London, UK / Mountain View, CA',
            'role_title': 'Research Scientist Resident',
            'focus_alignment': 'Neuro-Symbolic Reasoning & Multi-Omics pipelines'
        }
    })
    assert resp.status_code == 200, f"/api/twin/apply-lab failed: {resp.text}"
    lab_app = resp.json()
    assert len(lab_app.get('cover_letter', '')) > 200, "Cover letter too short"
    assert 'cold_outreach_email' in lab_app or 'cold_email_pitch' in lab_app, "Missing cold email"
    print(f"  [PASS] /api/twin/apply-lab generated cover letter & cold email pitch")

    # Chat with Mark's Twin
    resp = client.post('/api/twin/chat', json={
        'message': 'Mark, what is our next immediate priority for ClawBio and the PhD?'
    })
    assert resp.status_code == 200, f"/api/twin/chat failed: {resp.text}"
    chat_resp = resp.json()
    assert len(chat_resp.get('reply', '')) > 50, "Chat response too short"
    print(f"  [PASS] /api/twin/chat answered with twin persona ({len(chat_resp['reply'])} chars)")

    print("\n9. Testing Dynamic System-Wide AI Chat Endpoints...")
    # Reviewer #2 Rebuttal Chat
    resp = client.post('/api/reviewer/chat', json={
        'paper_title': 'UltraEdge KV-Cache Paper',
        'critique': {'critical_weaknesses': [{'area': 'Baselines', 'critique': 'Missing SOTA 2024 comparisons'}]},
        'message': 'How do I rebut Reviewer 2 about missing baselines without rerunning everything?'
    })
    assert resp.status_code == 200, f"Reviewer chat failed: {resp.text}"
    rev_chat = resp.json()
    assert len(rev_chat.get('reply', '')) > 50, "Reviewer chat too short"
    print(f"  [PASS] /api/reviewer/chat returned dynamic rebuttal coach response ({len(rev_chat['reply'])} chars)")

    # Novelty Radar Gap Deep-Dive Chat
    resp = client.post('/api/radar/chat', json={
        'topic': 'Multi-Omics Variant Annotation',
        'radar_result': {'unsolved_research_gaps': [{'title': 'ClinVar ACMG latency', 'description': 'Slow lookups'}]},
        'message': 'Propose an asynchronous mathematical formulation to solve this gap.'
    })
    assert resp.status_code == 200, f"Radar chat failed: {resp.text}"
    rad_chat = resp.json()
    assert len(rad_chat.get('reply', '')) > 50, "Radar chat too short"
    print(f"  [PASS] /api/radar/chat returned dynamic novelty guidance ({len(rad_chat['reply'])} chars)")

    # Paper Reader AI Mentor Chat
    resp_papers = client.get('/api/papers')
    assert resp_papers.status_code == 200
    papers_data = resp_papers.json()
    papers_list = papers_data.get('papers', []) if isinstance(papers_data, dict) else papers_data
    if papers_list:
        sample_pid = papers_list[0]['id']
        resp = client.post(f'/api/papers/{sample_pid}/chat', json={
            'message': 'Explain the core algorithmic mechanism of this paper in plain English.'
        })
        assert resp.status_code == 200, f"Paper chat failed: {resp.text}"
        p_chat = resp.json()
        assert len(p_chat.get('reply', '')) > 50, "Paper chat too short"
        print(f"  [PASS] /api/papers/{sample_pid}/chat returned AI Mentor explanation ({len(p_chat['reply'])} chars)")

    print("\n10. Testing Engine 07: GitHub Connector & Autonomous 'Check & Proceed' Application Pipeline...")
    # GitHub Status Check
    resp = client.get('/api/twin/github/status')
    assert resp.status_code == 200, f"/api/twin/github/status failed: {resp.text}"
    gh_status = resp.json()
    assert gh_status.get('username') == 'Febiri', "Username mismatch"
    print(f"  [PASS] /api/twin/github/status verified for @{gh_status['username']} (reachable: {gh_status.get('api_reachable')})")

    # GitHub Repos Live Fetch
    resp = client.get('/api/twin/github/repos')
    assert resp.status_code == 200, f"/api/twin/github/repos failed: {resp.text}"
    repos_data = resp.json()
    repos_list = repos_data.get('repos', [])
    assert len(repos_list) > 0, "No repos returned"
    print(f"  [PASS] /api/twin/github/repos returned {len(repos_list)} live repositories (e.g. {repos_list[0]['name']})")

    # Autonomous "Check & Proceed" Pre-Fill Preparation
    resp = client.post('/api/twin/prepare-application', json={
        'opportunity_type': 'grant',
        'title': 'Google PhD Fellowship in AI & Computational Biology',
        'details': {'organization': 'Google Research'}
    })
    assert resp.status_code == 200, f"/api/twin/prepare-application failed: {resp.text}"
    packet = resp.json()
    assert 'applicant_info' in packet, "Missing applicant_info"
    assert packet['applicant_info'].get('name') == 'Mark Febiri', "Name mismatch"
    assert 'form_autofill_script' in packet, "Missing form_autofill_script"
    assert 'dossier' in packet, "Missing dossier"
    print(f"  [PASS] /api/twin/prepare-application created pre-filled packet with autofill bookmarklet")

    # Execute Proceed Dispatch
    resp = client.post('/api/twin/dispatch-application', json={
        'packet': packet,
        'target_repo': 'febPhD'
    })
    assert resp.status_code == 200, f"/api/twin/dispatch-application failed: {resp.text}"
    dispatch_res = resp.json()
    assert dispatch_res.get('success') is True, "Dispatch failed"
    assert dispatch_res.get('status') == 'Dispatched', "Status mismatch"
    print(f"  [PASS] /api/twin/dispatch-application executed Proceed command (status: {dispatch_res['status']})")

    # Dispatch Audit History
    resp = client.get('/api/twin/dispatch-history')
    assert resp.status_code == 200, f"/api/twin/dispatch-history failed: {resp.text}"
    history_data = resp.json()
    assert history_data.get('total', 0) >= 1, "Dispatch history empty"
    print(f"  [PASS] /api/twin/dispatch-history returned {history_data['total']} logged applications")

    print("\nALL 10 DYNAMIC TEST SUITES PASSED FLAWLESSLY! 100% OPERATIONAL!")

if __name__ == '__main__':
    test_all()
