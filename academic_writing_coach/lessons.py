"""The systematic Learn course: ordered units, each with a lesson, a before/after example, and a checklist.

Units unlock in order. The first unit you have not completed is also the focus of the daily challenge.
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
    Unit(
        id="u01_precision",
        title="Precise sentences",
        skill="Write short, precise sentences that carry one clear idea each.",
        explanation=(
            "Academic readers look for the claim quickly. Remove filler such as 'very', 'in order to', "
            "'it is important to note that', and stacked adjectives. Replace vague verbs with specific ones."
        ),
        weak="In order to try to understand, it is very important to note that the data was looked at in a way that could be considered thorough.",
        strong="We analysed the data using a mixed-effects model to test the effect of temperature.",
        why_it_works="The strong version names the method and the purpose. Filler words add length but no information.",
        checklist=(
            "Remove 'very', 'really', 'in order to' and 'it is important to note that'.",
            "Each sentence carries one main idea.",
            "Verbs are specific: 'analysed', 'measured', 'compared' rather than 'looked at'.",
        ),
        practice_task="Rewrite a paragraph of three long, vague sentences about a survey so each sentence is short and precise.",
    ),
    Unit(
        id="u02_register",
        title="Formal register",
        skill="Choose formal academic words and avoid contractions and conversational phrases.",
        explanation=(
            "Academic writing avoids contractions, phrasal verbs where a single verb exists, and words "
            "like 'a lot of' or 'get'. Prefer 'demonstrate' to 'show', 'increase' to 'go up', and 'many' or 'a substantial number of' to 'a lot of'."
        ),
        weak="The results don't show much change, but a lot of people got better scores.",
        strong="The results did not demonstrate a substantial change, although a considerable number of participants improved their scores.",
        why_it_works="Formal verbs and quantifiers signal precision. Contractions and vague quantities signal conversation.",
        checklist=(
            "No contractions (don't, it's, can't).",
            "Replace 'a lot of' with a more precise quantifier.",
            "Replace phrasal verbs such as 'go up' or 'find out' with single formal verbs where possible.",
        ),
        practice_task="Rewrite a casual paragraph about a campus study, with at least three contractions and two phrasal verbs, in formal academic register.",
    ),
    Unit(
        id="u03_hedging",
        title="Hedging and stance",
        skill="Qualify claims with appropriate hedges such as may, suggest, and appear to.",
        explanation=(
            "Research claims are rarely certain. Hedges show that you understand the limits of your evidence. "
            "Use modal verbs ('may', 'could'), verbs ('suggest', 'indicate'), and adverbs ('possibly', 'largely')."
        ),
        weak="This proves that the new drug cures depression.",
        strong="These findings suggest that the new drug may reduce depressive symptoms in the short term.",
        why_it_works="The strong version matches the strength of the evidence. Over-claiming invites reviewer criticism.",
        checklist=(
            "At least one hedge on each main claim.",
            "No absolute words ('proves', 'always', 'never') unless the evidence is conclusive.",
            "Hedge strength matches the evidence: 'may' for weak, 'suggest' for moderate.",
        ),
        practice_task="Rewrite a paragraph that overstates the results of a small pilot study so that every claim is appropriately hedged.",
    ),
    Unit(
        id="u04_topic_sentences",
        title="Topic sentences and paragraph unity",
        skill="Open each paragraph with a topic sentence and keep every sentence on that topic.",
        explanation=(
            "A topic sentence states the paragraph's main point. The remaining sentences support, explain, or "
            "evidence that point. If a sentence introduces a new idea, start a new paragraph."
        ),
        weak="Water pollution is a serious problem. Many cities were founded near rivers. The factories also release heavy metals.",
        strong="Industrial effluent is the main source of heavy-metal pollution in urban rivers. Factories discharge untreated wastewater containing lead and mercury, which accumulates in sediments.",
        why_it_works="The strong version has one claim and only sentences that support it. The weak version drifts between three topics.",
        checklist=(
            "Each paragraph opens with a topic sentence that states one claim.",
            "Every sentence supports or explains that claim.",
            "No sentence introduces an unrelated idea.",
        ),
        practice_task="Write a paragraph about the effects of urban noise on sleep, with a clear topic sentence and three supporting sentences. Remove any off-topic sentence.",
    ),
    Unit(
        id="u05_cohesion",
        title="Cohesion and signposting",
        skill="Link ideas with precise transition words that show the logical relationship.",
        explanation=(
            "Transitions signal the relationship between ideas. 'However' and 'in contrast' show contrast; "
            "'consequently' and 'as a result' show cause; 'furthermore' and 'in addition' add information. "
            "Choose the relation that is actually true."
        ),
        weak="The sample was small. Also, the results were interesting. And we used a new method.",
        strong="The sample was small; however, the effect was consistent across all subgroups. Furthermore, the study introduced a new measurement method.",
        why_it_works="The transitions tell the reader how each sentence relates to the last one, so the argument is easier to follow.",
        checklist=(
            "Each transition matches the real relation: contrast, cause, addition, or example.",
            "No sentence starts with 'Also' or 'And' as the only link.",
            "At least two transitions in a paragraph of five or more sentences.",
        ),
        practice_task="Rewrite a paragraph of five unconnected sentences about a new bus route, adding accurate transitions that show contrast, cause, and addition.",
    ),
    Unit(
        id="u06_objectivity",
        title="Objective tone",
        skill="Keep a balanced academic tone by choosing when to use the passive or 'we' appropriately.",
        explanation=(
            "Many fields prefer an objective tone that focuses on the work rather than the author's opinion. "
            "The passive ('was measured') and 'we' for the authors' actions are both common. Avoid 'I think' "
            "and 'in my opinion' in formal writing."
        ),
        weak="I think the survey was really good and I believe everyone liked it.",
        strong="The survey was administered to 240 respondents, and 87% reported satisfaction with the service.",
        why_it_works="The strong version reports what was done and what was observed, without the author's belief.",
        checklist=(
            "No 'I think', 'I believe', or 'in my opinion' in the body text.",
            "Methods and results use the passive or 'we' for the authors' actions.",
            "Judgements are attributed to evidence or sources.",
        ),
        practice_task="Rewrite a paragraph describing a lab experiment written in first-person opinion ('I think', 'I believe') as an objective academic report.",
    ),
    Unit(
        id="u07_results",
        title="Reporting results",
        skill="Report results precisely, with the right tense and specific figures.",
        explanation=(
            "Report your own findings in the past tense and state the figure, the comparison, and the statistic. "
            "Use the present tense for established knowledge ('X increases Y'). Avoid interpreting results in the results section."
        ),
        weak="The new method is much better and things got a lot faster.",
        strong="The new method reduced processing time by 34% compared with the baseline (t(58) = 4.2, p < .001).",
        why_it_works="The strong version gives the magnitude, comparison, and evidence. Readers can check it.",
        checklist=(
            "Results are in the past tense.",
            "Each claim includes a figure, comparison, or statistic.",
            "Interpretation is kept for the discussion.",
        ),
        practice_task="Rewrite a vague paragraph reporting that a training programme 'worked well' into precise results with figures and a comparison group.",
    ),
    Unit(
        id="u08_citations",
        title="Integrating sources",
        skill="Paraphrase sources and introduce them with accurate reporting verbs.",
        explanation=(
            "Paraphrase the idea in your own words and cite it. Choose reporting verbs that match the source's stance: "
            "'argued', 'showed', 'proposed' for claims; 'suggested' or 'reported' for weaker ones. Do not copy phrases."
        ),
        weak="Climate change is a big problem for coastal cities (Smith, 2019).",
        strong="Smith (2019) argued that rising sea levels are likely to displace a substantial share of coastal populations by 2100.",
        why_it_works="The strong version names the author, reports their stance with a precise verb, and keeps the claim's specificity.",
        checklist=(
            "Each cited idea is paraphrased, not copied.",
            "The reporting verb matches the author's stance.",
            "Author and year are part of the sentence where the claim is discussed.",
        ),
        practice_task="Write two sentences introducing findings from two fictional studies on remote work productivity, using different reporting verbs that reflect their stance.",
    ),
    Unit(
        id="u09_argument",
        title="Counterargument and concession",
        skill="Acknowledge opposing views, then respond to them.",
        explanation=(
            "Strong academic arguments address the best objection. Use a concession ('Although', 'While it is true that') "
            "followed by a rebuttal ('the evidence nonetheless suggests'). This shows you know the debate."
        ),
        weak="Some people say the policy is expensive. But the policy works.",
        strong="While critics argue that the policy is costly, the cost per avoided hospital admission is lower than the cost of current care.",
        why_it_works="The concession shows the strongest objection, and the rebuttal answers it with evidence rather than assertion.",
        checklist=(
            "The opposing view is stated fairly and specifically.",
            "A concession word such as 'although' or 'while' is used.",
            "The rebuttal is backed by evidence or reasoning.",
        ),
        practice_task="Write a paragraph arguing for a university mental-health service. Include one fair objection about cost and a rebuttal with reasoning.",
    ),
    Unit(
        id="u10_structure",
        title="Structure of an abstract and introduction",
        skill="Use the standard moves: context, gap, aim, and contribution.",
        explanation=(
            "An introduction moves from broad context to a specific gap in knowledge, then states the aim and what the study adds. "
            "The gap sentence is often introduced with 'However', 'Little is known about', or 'To date, no study has'."
        ),
        weak="This study is about sleep. Sleep is important. We looked at sleep in students.",
        strong="Sleep duration is linked to academic performance in adolescents. However, little is known about whether this link holds for university students. This study examines sleep duration and exam performance in 412 first-year students.",
        why_it_works="The strong version follows the context, gap, aim pattern. Each sentence has a clear job.",
        checklist=(
            "Context sentence: the broad, accepted background.",
            "Gap sentence: what is missing, using a gap marker.",
            "Aim sentence: what this study does, specifically.",
        ),
        practice_task="Write a four-sentence introduction for a study of coffee consumption and sleep quality in shift workers, following context, gap, aim, and contribution.",
    ),
    Unit(
        id="u11_limitations",
        title="Limitations and future work",
        skill="State limitations honestly and propose specific, testable next steps.",
        explanation=(
            "Limitations show scientific maturity. State the weakness, explain its effect on the conclusion, and propose a remedy. "
            "Avoid vague future work such as 'more research is needed'."
        ),
        weak="The study had some limitations. More research is needed.",
        strong="The sample was limited to one university, so the findings may not generalise to other populations. Future work should replicate the design across multiple institutions.",
        why_it_works="The strong version names the limitation, its effect, and a specific next step.",
        checklist=(
            "Each limitation names its effect on the conclusion.",
            "Future work is specific and testable.",
            "The limitation is stated without excessive apology.",
        ),
        practice_task="Write a limitations paragraph for a study of 30 volunteers measuring a new app's effect on stress, naming the effect of each limitation and one specific next step.",
    ),
    Unit(
        id="u12_concision",
        title="Concision and revision",
        skill="Revise for word economy by removing redundancy and nominalisations.",
        explanation=(
            "Revise by removing repeated ideas, empty phrases, and nominalisations ('the performance of an analysis' becomes 'analysing'). "
            "Keep the meaning and the hedges, and cut everything else."
        ),
        weak="The performance of the implementation of the intervention resulted in an improvement in the outcome of participants.",
        strong="The intervention improved participants' outcomes.",
        why_it_works="The strong version keeps the subject and verb. Nominalisations hide the actor and add length.",
        checklist=(
            "Remove redundant phrases such as 'in order to' and 'the fact that'.",
            "Turn nominalisations back into verbs where natural.",
            "Keep all necessary hedges and citations.",
        ),
        practice_task="Revise a 90-word paragraph full of nominalisations and redundancy into a 50-word version without losing any claim.",
    ),
)

UNIT_IDS = tuple(unit.id for unit in UNITS)


def unit_by_id(unit_id: str) -> Unit:
    for unit in UNITS:
        if unit.id == unit_id:
            return unit
    raise KeyError(unit_id)
