import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import trestle.oscal.assessment_results as ar
from trestle.tasks.base_task import TaskBase
from trestle.tasks.base_task import TaskOutcome

logger = logging.getLogger(__name__)

class AwsConfigToOscal(TaskBase):
    """Task to convert AWS Config JSON output to OSCAL Assessment Results."""

    name = 'aws-config-to-oscal'

    def __init__(self, config_object: Optional[dict]) -> None:
        """Initialize the task with a configuration object."""
        super().__init__(config_object)

    def print_info(self) -> None:
        """Print the help string for the task."""
        logger.info(f'Help information for {self.name} task.')
        logger.info('Purpose: Transform AWS Config JSON into OSCAL Assessment Results.')

    def simulate(self) -> TaskOutcome:
        """Provide a simulated outcome for dry-runs."""
        logger.info(f"Simulating execution for {self.name}")
        return TaskOutcome('simulated-success')

    def execute(self) -> TaskOutcome:
        """Execute the AWS Config to OSCAL translation task."""
        try:
            input_file = Path(self._config.get('input-file'))
            output_dir = Path(self._config.get('output-dir'))
            output_dir.mkdir(parents=True, exist_ok=True)
            with open(input_file, 'r') as f:
                aws_data = json.load(f)

            eval_results = aws_data.get('EvaluationResults', [])
            observations = []
            findings = []
            for record in eval_results:
                identifier = record.get('EvaluationResultIdentifier', {})
                qualifier = identifier.get('EvaluationResultQualifier', {})
                
                rule_name = qualifier.get('ConfigRuleName', 'unknown-rule')
                resource_id = qualifier.get('ResourceId', 'unknown-resource')
                compliance = record.get('ComplianceType', 'NOT_APPLICABLE')
                timestamp = record.get('ResultRecordedTime', datetime.now(timezone.utc).isoformat())
                state = 'satisfied' if compliance == 'COMPLIANT' else 'not-satisfied'
                obs_uuid = str(uuid.uuid4())
                finding_uuid = str(uuid.uuid4())
                observations.append({
                    "uuid": obs_uuid,
                    "description": f"AWS Config evaluation for rule {rule_name}",
                    "methods": ["AUTOMATED"],
                    "collected": timestamp,
                    "subjects": [
                        {
                            "subject-uuid": str(uuid.uuid4()),
                            "type": "component",
                            "title": resource_id
                        }
                    ]
                })
                findings.append({
                    "uuid": finding_uuid,
                    "title": rule_name,
                    "description": f"AWS Compliance Status: {compliance}",
                    "target": {
                        "type": "objective-id", 
                        "target-id": resource_id.replace(":", "-").replace("/", "-"),
                        "status": {"state": state}
                    },
                    "related-observations": [
                        {"observation-uuid": obs_uuid}
                    ]
                })
            oscal_dict = {
                "uuid": str(uuid.uuid4()),
                "metadata": {
                    "title": "AWS Config to OSCAL",
                    "last-modified": datetime.now(timezone.utc).isoformat(),
                    "version": "1.0",
                    "oscal-version": "1.0.4"
                },
                "import-ap": {"href": "aws-config-assessment-plan"}, 
                "results": [
                    {
                        "uuid": str(uuid.uuid4()),
                        "title": "AWS Config Assessment Results",
                        "description": "Automated evaluation results exported from AWS Config.", 
                        "start": datetime.now(timezone.utc).isoformat(),
                        "reviewed-controls": {
                            "description": "Controls evaluated by AWS Config",
                            "control-selections": [
                                {
                                    "description": "AWS Config Rules",
                                    "include-all": {}
                                }
                            ]
                        },
                        "observations": observations,
                        "findings": findings
                    }
                ]
            }
            assessment_results = ar.AssessmentResults.parse_obj(oscal_dict)
            output_file = output_dir / "aws_assessment_results.json"
            safe_json_string = assessment_results.json(exclude_none=True, by_alias=True)
            final_json = {
                "assessment-results": json.loads(safe_json_string)
            }
            
            with open(output_file, 'w') as f:
                json.dump(final_json, f, indent=2)

            logger.info(f"Successfully generated OSCAL file at {output_file}")
            return TaskOutcome('success')

        except Exception as e:
            logger.error(f"Error executing aws-config-to-oscal task: {e}")
            return TaskOutcome('failure')
