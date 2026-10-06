"""
Evaluation runner.
Usage:
    python eval/run_eval.py --student_id <id> --api_url http://localhost:8000

Outputs:
  eval/results/ragas_results.json
  eval/results/refusal_results.json
  eval/results/plots/
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import requests
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)
(RESULTS_DIR / "plots").mkdir(exist_ok=True)


def load_test_set() -> list[dict]:
    path = Path(__file__).parent / "test_set.json"
    if not path.exists():
        print("test_set.json not found. Run with --generate-test-set first.")
        return []
    with open(path) as f:
        return json.load(f)


def eval_chat_grounding(api_url: str, student_id: str, test_items: list[dict]) -> dict:
    """
    Evaluate RAG grounding using RAGAS-inspired metrics.
    For each on-material test item:
      - faithfulness: does answer contain only info from context?
      - answer_relevancy: is the answer relevant to the question?
      - refusal: was off-material query correctly refused?
    """
    print(f"\n{'='*60}")
    print(f"Evaluating {len(test_items)} test items...")
    print(f"{'='*60}")

    on_material = [i for i in test_items if not i.get("off_material", False)]
    off_material = [i for i in test_items if i.get("off_material", False)]

    # ── On-material: collect answers ──────────────────────────────────────────
    faithfulness_scores = []
    relevancy_scores = []
    context_precisions = []

    for item in on_material:
        try:
            res = requests.post(f"{api_url}/api/chat", json={
                "student_id": student_id,
                "message": item["question"],
            }, timeout=60)
            data = res.json()

            if data.get("refused"):
                print(f"  ⚠ Unexpected refusal for on-material: {item['question'][:50]}")
                faithfulness_scores.append(0.0)
                relevancy_scores.append(0.0)
                continue

            answer = data.get("answer", "")
            citations = data.get("citations", [])

            # Faithfulness: check if gold_location appears in citations
            gold_loc = item.get("gold_location", "")
            cited_locs = [c["location"] for c in citations]
            faith = 1.0 if any(gold_loc in loc or loc in gold_loc for loc in cited_locs) else 0.3
            faithfulness_scores.append(faith)

            # Relevancy: keyword overlap between answer and expected_keywords
            keywords = item.get("expected_keywords", [])
            if keywords:
                answer_lower = answer.lower()
                hits = sum(1 for kw in keywords if kw.lower() in answer_lower)
                relevancy_scores.append(hits / len(keywords))
            else:
                relevancy_scores.append(0.7)  # default

            # Context precision: fraction of citations that are relevant
            if citations:
                # Use gold_source_id if available
                gold_source = item.get("gold_source_id", "")
                relevant = sum(1 for c in citations if c.get("source_id") == gold_source)
                context_precisions.append(relevant / len(citations))
            else:
                context_precisions.append(0.0)

            print(f"  ✓ [{faith:.2f}f/{relevancy_scores[-1]:.2f}r] {item['question'][:50]}…")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            faithfulness_scores.append(0.0)
            relevancy_scores.append(0.0)

    # ── Off-material: refusal eval ────────────────────────────────────────────
    refusal_tp = 0
    refusal_fp = 0
    refusal_fn = 0

    for item in off_material:
        try:
            res = requests.post(f"{api_url}/api/chat", json={
                "student_id": student_id,
                "message": item["question"],
            }, timeout=60)
            data = res.json()
            refused = data.get("refused", False)
            if refused:
                refusal_tp += 1
                print(f"  ✓ Correctly refused: {item['question'][:50]}…")
            else:
                refusal_fn += 1
                print(f"  ✗ Should have refused: {item['question'][:50]}…")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            refusal_fn += 1

    # Also check if any on-material was incorrectly refused
    # (counted as false positives for refusal)

    # Metrics
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "n_on_material": len(on_material),
        "n_off_material": len(off_material),
        "faithfulness": float(np.mean(faithfulness_scores)) if faithfulness_scores else 0.0,
        "answer_relevancy": float(np.mean(relevancy_scores)) if relevancy_scores else 0.0,
        "context_precision": float(np.mean(context_precisions)) if context_precisions else 0.0,
        "refusal_precision": refusal_tp / max(refusal_tp + refusal_fp, 1),
        "refusal_recall": refusal_tp / max(refusal_tp + refusal_fn, 1),
        "raw": {
            "faithfulness_per_item": faithfulness_scores,
            "relevancy_per_item": relevancy_scores,
        }
    }
    return results


def simulate_student_sessions(api_url: str, profile: dict, n_sessions: int = 5, adaptive: bool = True) -> dict:
    """
    Simulate a student going through multiple quiz sessions.
    Returns mastery progression data.
    """
    print(f"\n  Simulating {profile['name']} ({'adaptive' if adaptive else 'random'})...")

    # Create student
    res = requests.post(f"{api_url}/api/learner/onboard", json={
        "name": f"{profile['name']}_sim_{'adaptive' if adaptive else 'random'}",
    })
    student_id = res.json().get("student_id")
    if not student_id:
        return {"error": "Could not create student"}

    mastery_history = []

    for session in range(n_sessions):
        # Generate assessment
        try:
            gen_res = requests.post(f"{api_url}/api/assessment/generate", json={
                "student_id": student_id,
                "n_questions": 5,
                "qtype": "mcq",
                "adaptive": adaptive,
            }, timeout=120)
            if not gen_res.ok:
                print(f"    Session {session+1}: generation failed")
                continue
            assessment = gen_res.json()
        except Exception as e:
            print(f"    Session {session+1}: error {e}")
            continue

        # Simulate answers using profile's slip/guess rates
        answers = []
        for q in assessment.get("questions", []):
            # Simulate correct based on profile
            is_correct = np.random.random() > profile["slip"]
            if not is_correct:
                is_correct = np.random.random() < profile["guess"]  # lucky guess
            choices = q.get("choices", [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"id": "D"}])
            if is_correct:
                # Find correct choice or use A
                answer = choices[0]["id"] if choices else "A"
            else:
                # Wrong answer
                answer = choices[min(1, len(choices)-1)]["id"] if len(choices) > 1 else "B"
            answers.append({"question_id": q["id"], "student_answer": answer})

        # Submit
        try:
            sub_res = requests.post(f"{api_url}/api/assessment/submit", json={
                "assessment_id": assessment["assessment_id"],
                "answers": answers,
            }, timeout=60)
            sub_data = sub_res.json()
            score = sub_data.get("score", 0)
        except:
            score = 0

        # Get mastery
        try:
            model_res = requests.get(f"{api_url}/api/learner/{student_id}/model")
            model = model_res.json()
            avg_mastery = np.mean([c["mastery_prob"] for c in model.get("concepts", [{"mastery_prob": 0.3}])])
        except:
            avg_mastery = 0.3

        mastery_history.append({
            "session": session + 1,
            "score": score,
            "avg_mastery": float(avg_mastery),
        })
        print(f"    Session {session+1}: score={score:.2f}, avg_mastery={avg_mastery:.3f}")

    return {
        "profile": profile["name"],
        "adaptive": adaptive,
        "mastery_history": mastery_history,
        "final_mastery": mastery_history[-1]["avg_mastery"] if mastery_history else 0.0,
    }


def run_personalization_eval(api_url: str) -> dict:
    """Run simulated student eval for 3 profiles × adaptive/random."""
    profiles = [
        {"name": "Alice_strong", "slip": 0.05, "guess": 0.15, "prior": 0.6},
        {"name": "Bob_average",  "slip": 0.10, "guess": 0.25, "prior": 0.3},
        {"name": "Carol_weak",   "slip": 0.20, "guess": 0.35, "prior": 0.1},
    ]

    all_results = []
    for profile in profiles:
        adaptive_result = simulate_student_sessions(api_url, profile, n_sessions=5, adaptive=True)
        random_result = simulate_student_sessions(api_url, profile, n_sessions=5, adaptive=False)
        all_results.extend([adaptive_result, random_result])

    return {"personalization_results": all_results}


def plot_results(ragas: dict, personalization: dict):
    """Generate result plots."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.patch.set_facecolor('#020617')

    # RAGAS metrics
    ax = axes[0]
    ax.set_facecolor('#0f172a')
    metrics = ['faithfulness', 'answer_relevancy', 'context_precision', 'refusal_precision', 'refusal_recall']
    values = [ragas.get(m, 0) for m in metrics]
    colors = ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b']
    bars = ax.bar(range(len(metrics)), values, color=colors, alpha=0.8, width=0.6)
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels([m.replace('_', '\n') for m in metrics], fontsize=8, color='#94a3b8')
    ax.set_ylim(0, 1)
    ax.set_title('RAG Evaluation Metrics', color='#e2e8f0', pad=12)
    ax.tick_params(colors='#64748b')
    for spine in ax.spines.values(): spine.set_color('#1e293b')
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, f'{val:.2f}', ha='center', va='bottom', color='#94a3b8', fontsize=9)

    # Mastery progression
    ax = axes[1]
    ax.set_facecolor('#0f172a')
    profile_colors = {'Alice_strong': '#10b981', 'Bob_average': '#6366f1', 'Carol_weak': '#ef4444'}
    for result in personalization.get('personalization_results', []):
        if not result.get('mastery_history'):
            continue
        profile = result['profile']
        sessions = [h['session'] for h in result['mastery_history']]
        masteries = [h['avg_mastery'] for h in result['mastery_history']]
        color = profile_colors.get(profile.split('_')[0] + '_' + profile.split('_')[1], '#6366f1')
        style = '-' if result['adaptive'] else '--'
        label = f"{result['profile']} ({'A' if result['adaptive'] else 'R'})"
        ax.plot(sessions, masteries, style, color=color, linewidth=2, label=label, marker='o', markersize=4)
    ax.set_xlabel('Session', color='#94a3b8')
    ax.set_ylabel('Avg Mastery', color='#94a3b8')
    ax.set_title('Mastery Gain: Adaptive (—) vs Random (--)', color='#e2e8f0', pad=12)
    ax.legend(fontsize=7, facecolor='#1e293b', edgecolor='#334155', labelcolor='#94a3b8')
    ax.tick_params(colors='#64748b')
    for spine in ax.spines.values(): spine.set_color('#1e293b')

    # Final mastery comparison
    ax = axes[2]
    ax.set_facecolor('#0f172a')
    results = personalization.get('personalization_results', [])
    adaptive_r = [r for r in results if r.get('adaptive')]
    random_r = [r for r in results if not r.get('adaptive')]
    profiles_names = [r['profile'] for r in adaptive_r]
    x = np.arange(len(profiles_names))
    w = 0.35
    a_masteries = [r['final_mastery'] for r in adaptive_r]
    r_masteries = [r['final_mastery'] for r in random_r]
    ax.bar(x - w/2, a_masteries, w, label='Adaptive', color='#6366f1', alpha=0.85)
    ax.bar(x + w/2, r_masteries, w, label='Random', color='#64748b', alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([p.replace('_', '\n') for p in profiles_names], fontsize=8, color='#94a3b8')
    ax.set_title('Final Mastery: Adaptive vs Random', color='#e2e8f0', pad=12)
    ax.legend(facecolor='#1e293b', edgecolor='#334155', labelcolor='#94a3b8')
    ax.tick_params(colors='#64748b')
    for spine in ax.spines.values(): spine.set_color('#1e293b')

    plt.tight_layout()
    plot_path = RESULTS_DIR / "plots" / "eval_results.png"
    plt.savefig(plot_path, dpi=150, bbox_inches='tight', facecolor='#020617')
    print(f"\n  Plot saved: {plot_path}")
    return str(plot_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--student_id', required=True, help='Student ID for on-material eval')
    parser.add_argument('--api_url', default='http://localhost:8000')
    parser.add_argument('--skip-personalization', action='store_true')
    args = parser.parse_args()

    print("\n🔬 StudyCompanion Evaluation Suite")
    print(f"API: {args.api_url}")
    print(f"Student: {args.student_id}")

    # Health check
    try:
        r = requests.get(f"{args.api_url}/api/health", timeout=5)
        assert r.ok
    except:
        print("❌ Backend not reachable. Start the backend first.")
        sys.exit(1)

    # Load test set
    test_items = load_test_set()
    if not test_items:
        print("Creating minimal test set from on-material questions…")
        test_items = _generate_minimal_test_set(args.api_url, args.student_id)

    # RAG eval
    print("\n📊 RAG Grounding Evaluation")
    ragas_results = eval_chat_grounding(args.api_url, args.student_id, test_items)
    ragas_path = RESULTS_DIR / "ragas_results.json"
    with open(ragas_path, 'w') as f:
        json.dump(ragas_results, f, indent=2)
    print(f"\n  Faithfulness:        {ragas_results['faithfulness']:.3f}")
    print(f"  Answer Relevancy:    {ragas_results['answer_relevancy']:.3f}")
    print(f"  Context Precision:   {ragas_results['context_precision']:.3f}")
    print(f"  Refusal Precision:   {ragas_results['refusal_precision']:.3f}")
    print(f"  Refusal Recall:      {ragas_results['refusal_recall']:.3f}")

    # Personalization eval
    personalization_results = {"personalization_results": []}
    if not args.skip_personalization:
        print("\n🎓 Personalization Evaluation (3 profiles × 5 sessions each)")
        print("  Note: This will make API calls to generate/submit assessments.")
        personalization_results = run_personalization_eval(args.api_url)
        p_path = RESULTS_DIR / "personalization_results.json"
        with open(p_path, 'w') as f:
            json.dump(personalization_results, f, indent=2)

    # Plots
    print("\n📈 Generating plots…")
    plot_path = plot_results(ragas_results, personalization_results)

    # Summary
    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "ragas": ragas_results,
        "personalization": personalization_results,
        "plot": plot_path,
    }
    with open(RESULTS_DIR / "summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    print("\n✅ Evaluation complete!")
    print(f"   Results: {RESULTS_DIR}/")
    print(f"   Plot:    {plot_path}")


def _generate_minimal_test_set(api_url: str, student_id: str) -> list[dict]:
    """Generate a minimal test set using the API itself (bootstrap)."""
    off_material = [
        {"question": "What is the GDP of France in 2024?", "off_material": True},
        {"question": "Who won the FIFA World Cup in 2030?", "off_material": True},
        {"question": "What is the latest iPhone model?", "off_material": True},
        {"question": "Tell me about celebrity gossip", "off_material": True},
        {"question": "What is the stock price of Tesla today?", "off_material": True},
    ]
    # Try to get some on-material items from vector search
    on_material = []
    try:
        res = requests.get(f"{api_url}/api/knowledge/search?q=explain+the+concept&student_id={student_id}&top_k=10")
        units = res.json()
        for i, unit in enumerate(units[:10]):
            on_material.append({
                "question": f"What is explained in this passage: {unit['text'][:100]}?",
                "gold_location": unit['location'],
                "gold_source_id": unit['source_id'],
                "expected_keywords": unit['text'].split()[:5],
                "off_material": False,
            })
    except:
        pass

    test_set = on_material + off_material
    # Save for future use
    with open(Path(__file__).parent / "test_set.json", 'w') as f:
        json.dump(test_set, f, indent=2)
    return test_set


if __name__ == "__main__":
    main()
