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

    print("\nALL 8 TEST SUITES PASSED FLAWLESSLY! 100% OPERATIONAL!")

if __name__ == '__main__':
    test_all()
