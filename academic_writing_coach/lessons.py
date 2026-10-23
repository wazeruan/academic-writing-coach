"""The systematic Learn course for research-paper and technical-report writing.

Aimed at writers with an IELTS writing band around 6.5 (B2–C1): general English is solid, so the
units teach the conventions of papers and reports rather than basic grammar. Units unlock in
order, and the first unit you have not completed is also the focus of the daily challenge.
"""

from dataclasses import dataclass

PASS_SCORE = 70  # Overall score (0-100) needed to complete a unit.


@dataclass(frozen=True)
class Unit:
    id: str
    title: str
    skill: str
    explanation: str
    weak: str
    strong: str
    why_it_works: str
    checklist: tuple[str, ...]
    practice_task: str  # Offline fallback when the local model is unavailable.


UNITS: tuple[Unit, ...] = (
    # Part 1: sentence and paragraph foundations ------------------------------------
    Unit(
        id="u01_precision",
        title="Precise sentences",
        skill="Write short, specific sentences that carry one idea each.",
        explanation=(
            "Reviewers read quickly and look for concrete claims. Cut filler such as 'in order to', "
            "'a variety of', and 'it is worth noting that', and replace vague verbs like 'do' or 'look at' "
            "with specific ones such as 'evaluate', 'measure', or 'compare'."
        ),
        weak="In this paper, we try to do an investigation into how well the model is able to perform in a variety of different settings.",
        strong="We evaluate the model on four out-of-distribution benchmarks.",
        why_it_works="The strong version names the action and the scope in eight words. Every word carries information.",
        checklist=(
            "No filler phrases such as 'in order to', 'a variety of', or 'it is worth noting that'.",
            "Each sentence makes one main point.",
            "Verbs are specific: 'evaluate', 'measure', 'compare', not 'do' or 'look at'.",
        ),
        practice_task="Rewrite a 70-word paragraph from a machine-learning paper so that every sentence is short, specific, and free of filler.",
    ),
    Unit(
        id="u02_claims",
        title="Claim strength and hedging",
        skill="Match the strength of each claim to the strength of the evidence.",
        explanation=(
            "Over-claiming is the most common reason reviewers distrust a paper. Use strong verbs ('shows', "
            "'outperforms') only for what your experiments directly measure, and hedge interpretations "
            "('suggests', 'may', 'is consistent with'). State the scope: which data, which setting."
        ),
        weak="Our method solves the hallucination problem in language models.",
        strong="On TruthfulQA, our method reduces the hallucination rate by 18%, which suggests that retrieval grounding mitigates, but does not eliminate, the problem.",
        why_it_works="The strong version reports the measured result with its scope, then hedges the interpretation.",
        checklist=(
            "Measured results use direct verbs; interpretations use hedges.",
            "Each claim names its scope: dataset, setting, or condition.",
            "No absolute words ('solves', 'always', 'proves') without conclusive evidence.",
        ),
        practice_task="Rewrite a results paragraph that over-claims ('our model is the best', 'this proves') so each claim matches a small experiment on two datasets.",
    ),
    Unit(
        id="u03_paragraphs",
        title="Paragraph structure",
        skill="Open each paragraph with its point, support it, and close with the takeaway.",
        explanation=(
            "In papers, a reader should get the argument from the first sentence of each paragraph alone. "
            "Start with the claim, give evidence or reasoning, and end with what it means for your work. "
            "One paragraph, one point."
        ),
        weak="We used three datasets. Training took two days. The second dataset is noisy. Results are in Table 3. The model did well on most of them.",
        strong="Our model is robust to label noise. On the noisiest dataset (NoisyBench-40, with 40% label noise), accuracy drops by only 2.1 points, compared with 9.4 for the baseline (Table 3). This robustness matters because real annotation pipelines rarely produce clean labels.",
        why_it_works="The first sentence states the claim, the middle gives evidence, and the last says why it matters.",
        checklist=(
            "The first sentence states the paragraph's single point.",
            "The middle sentences give evidence or reasoning for that point.",
            "The last sentence states the takeaway or links to the next point.",
        ),
        practice_task="Write one paragraph arguing that your caching layer reduced API latency, with a topic sentence, two pieces of evidence, and a takeaway.",
    ),
    Unit(
        id="u04_cohesion",
        title="Flow and signposting",
        skill="Link sentences so each one builds on the last, and signpost the structure.",
        explanation=(
            "Readers follow text best when each sentence starts with known information and ends with new "
            "information. Use precise links ('however', 'as a result', 'in contrast') only for the relation "
            "that is true, and signpost structure ('First,', 'Section 4 describes')."
        ),
        weak="Transformers need a lot of memory. Long documents are a problem. Sparse attention is one approach. We use a sliding window.",
        strong="Transformers need memory quadratic in sequence length, which makes long documents expensive. This memory cost can be reduced with sparse attention, which restricts which tokens attend to each other. We adopt one such pattern: a sliding window of 512 tokens, described in Section 3.",
        why_it_works="Each sentence picks up the idea that ended the previous one, so the reader never has to guess the connection.",
        checklist=(
            "Each sentence begins with information the reader already has.",
            "Each linking word expresses the true relation: contrast, cause, or addition.",
            "The structure is signposted where a reader could get lost.",
        ),
        practice_task="Rewrite five disconnected sentences about why a data pipeline was migrated to a streaming system into one flowing paragraph.",
    ),
    # Part 2: the research paper -------------------------------------------------------
    Unit(
        id="u05_abstract",
        title="The abstract",
        skill="Write an abstract that states the problem, the gap, the method, the main result, and why it matters.",
        explanation=(
            "Most readers decide from the abstract alone. Use one paragraph with five moves: problem, gap, "
            "what you did, the main quantitative result, and the implication. Give at least one number, "
            "and avoid citations and undefined abbreviations."
        ),
        weak="Large language models are very popular. In this paper we propose a new method. We did many experiments and the results are good.",
        strong="Fine-tuning large language models is expensive, and existing parameter-efficient methods still update millions of weights. We propose SparseAdapt, which updates only the 0.1% of weights with the largest gradients. On five reasoning benchmarks, SparseAdapt matches full fine-tuning within 0.5 points while using 40% less GPU memory. This makes adaptation feasible on a single consumer GPU.",
        why_it_works="Each sentence performs one move, and the result is a concrete number with a comparison.",
        checklist=(
            "All five moves are present: problem, gap, method, result, implication.",
            "The main result is given as a number with a comparison.",
            "No citations, no undefined abbreviations, one paragraph.",
        ),
        practice_task="Write a 150-word abstract for a study showing that deduplicating pretraining data improves a code model's pass@1 by 4 points.",
    ),
    Unit(
        id="u06_introduction",
        title="Introduction and contributions",
        skill="Move from context to a specific gap, state your approach, and list your contributions.",
        explanation=(
            "A strong introduction narrows quickly: broad context, a specific gap ('However, existing methods "
            "assume…'), your idea in one sentence, and an explicit contribution list. Each contribution "
            "should be checkable against the paper."
        ),
        weak="Deep learning is used in many areas. There are many problems. In this paper we study some of them and show some results.",
        strong="Reinforcement learning agents often fail when deployed in environments that differ slightly from training. However, existing robustness benchmarks vary only visual appearance, not dynamics. We introduce DynShift, a benchmark that perturbs physical parameters. Our contributions are: (1) a suite of 12 tasks with controlled dynamics shifts; (2) an evaluation of six algorithms; and (3) evidence that domain randomisation does not transfer to unseen dynamics.",
        why_it_works="The gap is specific, the idea is one sentence, and each contribution can be verified in the paper.",
        checklist=(
            "The gap is specific and marked ('However', 'existing work assumes').",
            "Your approach is stated in one sentence.",
            "Contributions are listed explicitly and are each verifiable.",
        ),
        practice_task="Write a 180-word introduction for a paper on reducing the inference latency of a speech-recognition model on mobile phones, ending with three contributions.",
    ),
    Unit(
        id="u07_related_work",
        title="Related work and positioning",
        skill="Group prior work by theme, then state how your work differs.",
        explanation=(
            "Related work is an argument, not a list. Group papers by approach, summarise what each group does "
            "and where it falls short, and end each group with how your work differs ('Unlike these methods, "
            "we…'). Use reporting verbs that match the source: 'showed', 'proposed', 'argued'."
        ),
        weak="Smith et al. (2021) did pruning. Lee et al. (2022) did quantisation. Chen et al. (2023) also did quantisation.",
        strong="Model compression methods fall into two groups. Pruning methods remove redundant weights (Smith et al., 2021), but the pruning ratio is usually chosen for a single hardware target. Quantisation methods reduce weight precision (Lee et al., 2022; Chen et al., 2023), but they fix the bit width before deployment. Unlike both, we choose the compression level at run time from the available memory.",
        why_it_works="The strong version groups by approach, names each group's limitation, and positions the new work against them.",
        checklist=(
            "Prior work is grouped by theme, not listed paper by paper.",
            "Each group's limitation is stated.",
            "Your work is positioned explicitly ('Unlike…, we…').",
        ),
        practice_task="Write a related-work paragraph on two approaches to retrieval-augmented generation (fictional citations allowed) and position a new method that retrieves at every decoding step.",
    ),
    Unit(
        id="u08_methods",
        title="Describing methods and systems",
        skill="Describe a method precisely enough that another researcher could reproduce it.",
        explanation=(
            "Define every symbol before you use it, give all settings that affect results (hyperparameters, "
            "data splits, hardware), and keep one name for each concept throughout. Describe what was done "
            "in the past tense or with 'we'; describe how the system works in the present tense."
        ),
        weak="We trained the model with some standard settings for a while until it was good, using the usual optimiser.",
        strong="We trained the model for 50 epochs with AdamW (learning rate 3e-4, weight decay 0.01, batch size 128) on a single A100 GPU, selecting the checkpoint with the lowest validation loss.",
        why_it_works="Every setting that affects the result is stated, so the experiment can be repeated.",
        checklist=(
            "Every symbol and abbreviation is defined at first use.",
            "All settings that affect results are given with values.",
            "Each concept keeps one name throughout.",
        ),
        practice_task="Describe the training setup of a small image classifier (data split, optimiser, schedule, hardware, model selection) so that it could be reproduced.",
    ),
    Unit(
        id="u09_results",
        title="Reporting experimental results",
        skill="Report results with the comparison, the metric, the number, and its uncertainty.",
        explanation=(
            "Lead with the finding, then the evidence: which method, compared with what, on which metric, "
            "by how much, and how reliable the difference is (standard deviation over seeds, or a test). "
            "Point to the table or figure, and keep interpretation for the discussion."
        ),
        weak="As you can see in the table, our method is much better than the others in almost all cases.",
        strong="Our method achieves the highest mean F1 on four of five datasets (Table 2), with an average gain of 2.3 points over the strongest baseline (±0.4 over five seeds).",
        why_it_works="It states the comparison, metric, size of the gain, its variance, and where to find the evidence.",
        checklist=(
            "Each result names the comparison and the metric.",
            "Gains are given as numbers with uncertainty (seeds, intervals, or tests).",
            "Tables and figures are referenced, and interpretation is kept for later.",
        ),
        practice_task="Write a results paragraph comparing a new anomaly detector with two baselines on three datasets, using precision, recall, and variance over three seeds.",
    ),
    Unit(
        id="u10_figures",
        title="Figures, tables, and captions",
        skill="Write captions and references that tell the reader what to notice.",
        explanation=(
            "A caption should state the takeaway, not only the content: 'Accuracy drops sharply beyond 4k tokens' "
            "is more useful than 'Accuracy versus length'. Define axes, units, and abbreviations, and refer "
            "to every figure in the text with the point it supports."
        ),
        weak="Figure 3: Results. The figure shows the results of the experiment.",
        strong="Figure 3: Validation loss versus training steps. Our curriculum (blue) converges in 40% fewer steps than random ordering (grey); shaded regions show ±1 standard deviation over five seeds.",
        why_it_works="The caption explains the axes, the comparison, the takeaway, and what the shading means.",
        checklist=(
            "The caption states the takeaway, not only the topic.",
            "Axes, units, colours, and error bars are explained.",
            "The text refers to the figure with the point it supports.",
        ),
        practice_task="Write a caption and one referencing sentence for a table comparing the memory use and throughput of three serving frameworks.",
    ),
    Unit(
        id="u11_discussion",
        title="Discussion and limitations",
        skill="Interpret results, admit limitations with their effect, and propose specific next steps.",
        explanation=(
            "The discussion explains why the results came out as they did and what they imply. State each "
            "limitation, say how it affects the conclusion, and propose a concrete next step. "
            "'More research is needed' says nothing."
        ),
        weak="Our study has some limitations. More research is needed in the future.",
        strong="Our method gains most on long documents, which suggests that retrieval helps most when the relevant information lies far from the question. However, all experiments use English benchmarks, so the gains may not hold for morphologically rich languages. Evaluating on the multilingual FLORES suite would test this directly.",
        why_it_works="It interprets a result instead of repeating it, names a limitation and its effect on the claim, and proposes a specific test.",
        checklist=(
            "Results are interpreted, not repeated.",
            "Each limitation states its effect on the conclusions.",
            "Future work is specific and testable.",
        ),
        practice_task="Write a limitations paragraph for an RL study evaluated in simulation only, with three random seeds and one robot type.",
    ),
    # Part 3: the technical report -----------------------------------------------------
    Unit(
        id="u12_exec_summary",
        title="Executive summary",
        skill="Put the conclusion and recommendation first, with the key numbers, for a busy reader.",
        explanation=(
            "A technical report's summary is read by people who may read nothing else. Start with the bottom "
            "line: what was found and what you recommend. Give the two or three numbers that justify it, "
            "then the main risk. Save background and method for later sections."
        ),
        weak="This report describes the work that the team did over the last quarter on the database. First we looked at the old system, then we tried several things.",
        strong="We recommend migrating the order database to PostgreSQL 16 by March. In load tests, p95 query latency fell from 340 ms to 85 ms, and hosting cost would drop by about 30%. The main risk is a 4-hour write freeze during cut-over, which we propose to schedule on a Sunday.",
        why_it_works="The decision comes first, two numbers justify it, and the main risk is named with a mitigation.",
        checklist=(
            "The recommendation or main finding is in the first sentence.",
            "Two or three key numbers support it.",
            "The main risk or cost is stated with a mitigation.",
        ),
        practice_task="Write a 120-word executive summary recommending whether to replace a rule-based spam filter with a fine-tuned classifier, using invented evaluation numbers.",
    ),
    Unit(
        id="u13_tradeoffs",
        title="Design decisions and trade-offs",
        skill="Justify a technical choice by comparing options against explicit criteria.",
        explanation=(
            "Reviewers of design documents want to know why you chose this option over the alternatives. "
            "Name the criteria first (latency, cost, maintainability), compare the options on each, state "
            "the choice, and acknowledge what you give up."
        ),
        weak="We chose Redis because it is fast and popular and everyone uses it.",
        strong="We compared Redis and Memcached on three criteria: read latency, persistence, and operational cost. Both met the 2 ms latency target, and their operational costs were within 5% of each other. Only Redis supports persistence, which we need to survive restarts. We accept its higher memory overhead (about 15% in our tests) in exchange.",
        why_it_works="The criteria are explicit, the comparison is evidence-based, and the cost of the choice is acknowledged.",
        checklist=(
            "The decision criteria are stated before the comparison.",
            "At least two options are compared on each criterion.",
            "The cost or downside of the chosen option is acknowledged.",
        ),
        practice_task="Write a paragraph justifying a choice between synchronous REST calls and a message queue for an order-processing service, with explicit criteria.",
    ),
    Unit(
        id="u14_revision",
        title="Concision and revision",
        skill="Revise drafts by cutting redundancy, turning nouns back into verbs, and keeping terms consistent.",
        explanation=(
            "First drafts hide actions inside nouns ('perform an evaluation of') and repeat ideas. Revise by "
            "restoring verbs ('evaluate'), deleting repetition, and checking that each concept keeps one name. "
            "Keep the hedges and numbers; cut everything else that adds no meaning."
        ),
        weak="The performance of an evaluation of the proposed approach was carried out, and the results of this evaluation showed an improvement in the accuracy of the model.",
        strong="We evaluated the proposed approach and found that it improves model accuracy.",
        why_it_works="The strong version restores the verbs and removes repetition while keeping the claim.",
        checklist=(
            "Nominalisations are turned back into verbs where natural.",
            "No idea is stated twice.",
            "Each concept keeps one name throughout.",
        ),
        practice_task="Revise a 100-word methods paragraph full of nominalisations and repeated phrases into about 60 words without losing any detail.",
    ),
)

UNIT_IDS = tuple(unit.id for unit in UNITS)


def unit_by_id(unit_id: str) -> Unit:
    for unit in UNITS:
        if unit.id == unit_id:
            return unit
    raise KeyError(unit_id)
