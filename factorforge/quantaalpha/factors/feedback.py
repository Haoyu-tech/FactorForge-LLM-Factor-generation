import json
from pathlib import Path

import pandas as pd
from jinja2 import Environment, StrictUndefined

from quantaalpha.core.experiment import Experiment
from quantaalpha.core.prompts import Prompts
from quantaalpha.core.proposal import (
    Hypothesis,
    HypothesisExperiment2Feedback,
    HypothesisFeedback,
    Trace,
)
from quantaalpha.log import logger
from quantaalpha.llm.client import APIBackend, robust_json_parse
from quantaalpha.utils import convert2bool

# Max retries for JSON parsing
MAX_JSON_PARSE_RETRIES = 3


def _build_factor_feedback(response_json: dict) -> HypothesisFeedback:
    feedback = HypothesisFeedback(
        observations=response_json.get("Observations", "No observations provided"),
        hypothesis_evaluation=response_json.get("Feedback for Hypothesis", "No feedback provided"),
        new_hypothesis=response_json.get("New Hypothesis", "No new hypothesis provided"),
        reason=response_json.get("Reasoning", "No reasoning provided"),
        decision=convert2bool(response_json.get("Replace Best Result", "no")),
    )
    explanations = response_json.get("Factor Explanations", {})
    feedback.factor_explanations = explanations if isinstance(explanations, dict) else {}
    return feedback


base_feedback_prompts = Prompts(file_path=Path(__file__).parent / "prompts" / "prompts.yaml")
DIRNAME = Path(__file__).absolute().resolve().parent


def _important_metric_names(index) -> list[str]:
    legacy = {
        "1day.excess_return_without_cost.max_drawdown",
        "1day.excess_return_without_cost.information_ratio",
        "1day.excess_return_without_cost.annualized_return",
        "IC", "ICIR", "Rank IC", "Rank ICIR",
    }
    selected = []
    for raw in index:
        metric = str(raw)
        if (
            metric in legacy
            or ".long." in metric
            or ".short." in metric
            or ".long_short." in metric
            or ".decile_" in metric
            or ".group_" in metric
            or ".asset_pricing." in metric
            or metric.startswith("factor.")
        ):
            selected.append(raw)
    return selected


def _result_frame(result, column_name: str) -> pd.DataFrame:
    frame = pd.DataFrame(result)
    frame.index.name = "metric"
    if len(frame.columns):
        frame = frame.rename(columns={frame.columns[0]: column_name})
    else:
        frame[column_name] = 0.0
    metrics = _important_metric_names(frame.index)
    return frame.loc[metrics] if metrics else frame


def process_results(current_result, sota_result):
    """Expose IC plus net long/short/long-short and decile metrics to the LLM."""
    current_df = _result_frame(current_result, "Current Result")
    if sota_result is None or (isinstance(sota_result, pd.DataFrame) and sota_result.empty):
        return current_df.to_string()

    sota_df = _result_frame(sota_result, "SOTA Result")
    combined = pd.concat([current_df, sota_df], axis=1)
    current = pd.to_numeric(combined.get("Current Result"), errors="coerce")
    sota = pd.to_numeric(combined.get("SOTA Result"), errors="coerce")
    combined[
        "Numerically larger result (interpret metric direction separately)"
    ] = current.gt(sota).map({True: "Current Result", False: "SOTA Result"})
    return combined.to_string()


class QlibFactorHypothesisExperiment2Feedback(HypothesisExperiment2Feedback):
    def generate_feedback(self, exp: Experiment, hypothesis: Hypothesis, trace: Trace) -> HypothesisFeedback:
        """
        Generate feedback for the given experiment and hypothesis.

        Args:
            exp (QlibFactorExperiment): The experiment to generate feedback for.
            hypothesis (QlibFactorHypothesis): The hypothesis to generate feedback for.
            trace (Trace): The trace of the experiment.

        Returns:
            Any: The feedback generated for the given experiment and hypothesis.
        """
        logger.info("Generating feedback...")
        hypothesis_text = hypothesis.hypothesis
        current_result = exp.result
        tasks_factors = [task.get_task_information_and_implementation_result() for task in exp.sub_tasks]
        # Safely get SOTA result, handle case where based_experiments might be empty or result is None
        sota_result = None
        if exp.based_experiments and len(exp.based_experiments) > 0:
            sota_result = exp.based_experiments[-1].result

        # Process the results to filter important metrics
        combined_result = process_results(current_result, sota_result)

        # Generate the system prompt
        sys_prompt = (
            Environment(undefined=StrictUndefined)
            .from_string(base_feedback_prompts["factor_feedback_generation"]["system"])
            .render(scenario=self.scen.get_scenario_all_desc())
        )

        # Generate the user prompt
        usr_prompt = (
            Environment(undefined=StrictUndefined)
            .from_string(base_feedback_prompts["factor_feedback_generation"]["user"])
            .render(
                hypothesis_text=hypothesis_text,
                task_details=tasks_factors,
                combined_result=combined_result,
            )
        )

        # Call the APIBackend to generate the response for hypothesis feedback with retry
        response_json = None
        last_error = None
        
        for attempt in range(MAX_JSON_PARSE_RETRIES):
            try:
                response = APIBackend().build_messages_and_create_chat_completion(
                    user_prompt=usr_prompt,
                    system_prompt=sys_prompt,
                    json_mode=True,
                )
                # Parse the JSON response using robust parser
                response_json = robust_json_parse(response)
                break
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"[QuantaAlpha] JSON parse failed (attempt {attempt + 1}/{MAX_JSON_PARSE_RETRIES}): {e}")
                if attempt < MAX_JSON_PARSE_RETRIES - 1:
                    logger.info("[QuantaAlpha] Re-requesting LLM...")
                continue
        
        if response_json is None:
            logger.error(f"[QuantaAlpha] JSON parse still failed after {MAX_JSON_PARSE_RETRIES} attempts")
            return HypothesisFeedback(
                observations="JSON parse failed; could not extract feedback",
                hypothesis_evaluation="Unable to evaluate",
                new_hypothesis="",
                reason=f"JSON parse error: {last_error}",
                decision=False,
            )

        return _build_factor_feedback(response_json)



qa_feedback_prompts = Prompts(file_path=Path(__file__).parent / "prompts" / "prompts.yaml")
class AlphaAgentQlibFactorHypothesisExperiment2Feedback(HypothesisExperiment2Feedback):
    def generate_feedback(self, exp: Experiment, hypothesis: Hypothesis, trace: Trace) -> HypothesisFeedback:
        """
        Generate feedback for the given experiment and hypothesis.

        Args:
            exp (QlibFactorExperiment): The experiment to generate feedback for.
            hypothesis (QlibFactorHypothesis): The hypothesis to generate feedback for.
            trace (Trace): The trace of the experiment.

        Returns:
            Any: The feedback generated for the given experiment and hypothesis.
        """
        logger.info("Generating feedback...")
        hypothesis_text = hypothesis.hypothesis
        current_result = exp.result
        tasks_factors = [task.get_task_information_and_implementation_result() for task in exp.sub_tasks]
        # Safely get SOTA result, handle case where based_experiments might be empty or result is None
        sota_result = None
        if exp.based_experiments and len(exp.based_experiments) > 0:
            sota_result = exp.based_experiments[-1].result

        # Extract complexity information by directly calculating from factor expressions
        # Import complexity calculation functions
        try:
            from quantaalpha.factors.coder.factor_ast import (
                calculate_symbol_length, count_base_features
            )
            from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
            
            for idx, task_detail in enumerate(tasks_factors):
                if idx < len(exp.sub_tasks):
                    task = exp.sub_tasks[idx]
                    factor_expr = task_detail.get("factor_expression", "")
                    if factor_expr:
                        complexity_warnings = []
                        # Calculate symbol length
                        symbol_length = calculate_symbol_length(factor_expr)
                        symbol_length_threshold = getattr(FACTOR_COSTEER_SETTINGS, 'symbol_length_threshold', 300)
                        if symbol_length > symbol_length_threshold:
                            complexity_warnings.append(
                                f"Symbol Length (SL) Check Failed: Symbol length ({symbol_length}) exceeds threshold ({symbol_length_threshold}). "
                                f"The factor expression is too complex and may lead to overfitting."
                            )
                        
                        # Calculate base features count
                        num_base_features = count_base_features(factor_expr)
                        base_features_threshold = getattr(FACTOR_COSTEER_SETTINGS, 'base_features_threshold', 6)
                        if num_base_features > base_features_threshold:
                            complexity_warnings.append(
                                f"Base Features Count (ER) Check Failed: Number of base features ({num_base_features}) exceeds threshold ({base_features_threshold}). "
                                f"The factor uses too many raw features, which may indicate over-engineering."
                            )
                        
                        if complexity_warnings:
                            task_detail["complexity_feedback"] = "\n".join(complexity_warnings)
        except Exception as e:
            logger.warning(f"Failed to calculate complexity info: {e}")

        # Process the results to filter important metrics
        combined_result = process_results(current_result, sota_result)

        # Generate the system prompt
        sys_prompt = (
            Environment(undefined=StrictUndefined)
            .from_string(qa_feedback_prompts["factor_feedback_generation"]["system"])
            .render(scenario=self.scen.get_scenario_all_desc())
        )

        # Generate the user prompt
        usr_prompt = (
            Environment(undefined=StrictUndefined)
            .from_string(qa_feedback_prompts["factor_feedback_generation"]["user"])
            .render(
                hypothesis_text=hypothesis_text,
                task_details=tasks_factors,
                combined_result=combined_result,
            )
        )

        # Call the APIBackend to generate the response for hypothesis feedback with retry
        response_json = None
        last_error = None
        
        for attempt in range(MAX_JSON_PARSE_RETRIES):
            try:
                response = APIBackend().build_messages_and_create_chat_completion(
                    user_prompt=usr_prompt,
                    system_prompt=sys_prompt,
                    json_mode=True,
                )
                # Parse the JSON response using robust parser
                response_json = robust_json_parse(response)
                break
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"[AlphaAgent] JSON parse failed (attempt {attempt + 1}/{MAX_JSON_PARSE_RETRIES}): {e}")
                if attempt < MAX_JSON_PARSE_RETRIES - 1:
                    logger.info("[AlphaAgent] Re-requesting LLM...")
                continue
        
        if response_json is None:
            logger.error(f"[AlphaAgent] JSON parse still failed after {MAX_JSON_PARSE_RETRIES} attempts")
            return HypothesisFeedback(
                observations="JSON parse failed; could not extract feedback",
                hypothesis_evaluation="Unable to evaluate",
                new_hypothesis="",
                reason=f"JSON parse error: {last_error}",
                decision=False,
            )

        return _build_factor_feedback(response_json)


class QlibModelHypothesisExperiment2Feedback(HypothesisExperiment2Feedback):
    """Generated feedbacks on the hypothesis from **Executed** Implementations of different tasks & their comparisons with previous performances"""

    def generate_feedback(self, exp: Experiment, hypothesis: Hypothesis, trace: Trace) -> HypothesisFeedback:
        """
        The `ti` should be executed and the results should be included, as well as the comparison between previous results (done by LLM).
        For example: `mlflow` of Qlib will be included.
        """

        logger.info("Generating feedback...")
        # Define the system prompt for hypothesis feedback
        system_prompt = feedback_prompts["model_feedback_generation"]["system"]

        # Define the user prompt for hypothesis feedback
        context = trace.scen
        SOTA_hypothesis, SOTA_experiment = trace.get_sota_hypothesis_and_experiment()

        user_prompt = (
            Environment(undefined=StrictUndefined)
            .from_string(feedback_prompts["model_feedback_generation"]["user"])
            .render(
                context=context,
                last_hypothesis=SOTA_hypothesis,
                last_task=SOTA_experiment.sub_tasks[0].get_task_information() if SOTA_hypothesis else None,
                last_code=SOTA_experiment.sub_workspace_list[0].code_dict.get("model.py") if SOTA_hypothesis else None,
                last_result=SOTA_experiment.result if SOTA_hypothesis else None,
                hypothesis=hypothesis,
                exp=exp,
            )
        )

        # Call the APIBackend to generate the response for hypothesis feedback with retry
        response_json_hypothesis = None
        last_error = None
        
        for attempt in range(MAX_JSON_PARSE_RETRIES):
            try:
                response_hypothesis = APIBackend().build_messages_and_create_chat_completion(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    json_mode=True,
                )
                # Parse the JSON response using robust parser
                response_json_hypothesis = robust_json_parse(response_hypothesis)
                break
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"[Model] JSON parse failed (attempt {attempt + 1}/{MAX_JSON_PARSE_RETRIES}): {e}")
                if attempt < MAX_JSON_PARSE_RETRIES - 1:
                    logger.info("[Model] Re-requesting LLM...")
                continue
        
        if response_json_hypothesis is None:
            logger.error(f"[Model] JSON parse still failed after {MAX_JSON_PARSE_RETRIES} attempts")
            return HypothesisFeedback(
                observations="JSON parse failed; could not extract feedback",
                hypothesis_evaluation="Unable to evaluate",
                new_hypothesis="",
                reason=f"JSON parse error: {last_error}",
                decision=False,
            )
        
        return HypothesisFeedback(
            observations=response_json_hypothesis.get("Observations", "No observations provided"),
            hypothesis_evaluation=response_json_hypothesis.get("Feedback for Hypothesis", "No feedback provided"),
            new_hypothesis=response_json_hypothesis.get("New Hypothesis", "No new hypothesis provided"),
            reason=response_json_hypothesis.get("Reasoning", "No reasoning provided"),
            decision=convert2bool(response_json_hypothesis.get("Decision", "false")),
        )
