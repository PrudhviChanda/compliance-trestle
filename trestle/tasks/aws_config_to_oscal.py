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
        logger.info('Purpose: Transform an entire directory of AWS Config JSON files into a unified OSCAL Assessment Results document.')

    def simulate(self) -> TaskOutcome:
        """Provide a simulated outcome for dry-runs."""
        logger.info(f"Simulating execution for {self.name}")
        return TaskOutcome.SIMULATED_SUCCESS

    def execute(self) -> TaskOutcome:
        """Execute the AWS Config to OSCAL translation task."""
        try:
            # 1. Dynamic Configuration Variables
            input_dir_str = self._config.get('input-dir')
            if not input_dir_str:
                logger.error("Configuration 'input-dir' is required.")
                return TaskOutcome.FAILURE
                
            input_dir = Path(input_dir_str)
            output_dir = Path(self._config.get('output-dir', 'oscal_output'))
            output_filename = self._config.get('output-filename', 'aws_assessment_results.json')
            oscal_version = self._config.get('oscal-version', '1.0.4')
            metadata_title = self._config.get('metadata-title', 'AWS Config Assessment')
            ap_href = self._config.get('assessment-plan-href', 'system-assessment-plan')
            
            if not input_dir.is_dir():
                logger.error(f"Input directory does not exist or is not a directory: {input_dir}")
                return TaskOutcome.FAILURE

            output_dir.mkdir(parents=True, exist_ok=True)
            
            observations = []
            findings = []
            
            # 2. Iterate through ALL JSON files in the input directory
            processed_files = 0
            for aws_file in input_dir.glob('*.json'):
                processed_files += 1
                with open(aws_file, 'r') as f:
                    try:
                        aws_data = json.load(f)
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse JSON in file: {aws_file}. Skipping.")
                        continue

                eval_results = aws_data.get('EvaluationResults', [])
                
                for record in eval_results:
                    identifier = record.get('EvaluationResultIdentifier', {})
                    qualifier = identifier.get('EvaluationResultQualifier', {})
                    
                    rule_name = qualifier.get('ConfigRuleName', 'unknown-rule')
                    resource_id = qualifier.get('ResourceId', 'unknown-resource')
                    compliance = record.get('ComplianceType', 'NOT_APPLICABLE')
                    timestamp = record.get('ResultRecordedTime', datetime.now(timezone.utc).isoformat())
                    
                    # Map AWS states to OSCAL states
                    if compliance == 'COMPLIANT':
                        state = 'satisfied'
                    elif compliance == 'NON_COMPLIANT':
                        state = 'not-satisfied'
                    else:
                        state = 'other'

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

            if processed_files == 0:
                logger.warning(f"No JSON files found in directory: {input_dir}")
                return TaskOutcome.FAILURE

            if not findings:
                logger.warning("No EvaluationResults found in any of the processed AWS Config JSON files.")
                return TaskOutcome.FAILURE

            # 3. Apply Dynamic Variables to OSCAL Object
            oscal_dict = {
                "uuid": str(uuid.uuid4()),
                "metadata": {
                    "title": metadata_title,
                    "last-modified": datetime.now(timezone.utc).isoformat(),
                    "version": "1.0",
                    "oscal-version": oscal_version
                },
                "import-ap": {"href": ap_href}, 
                "results": [
                    {
                        "uuid": str(uuid.uuid4()),
                        "title": "AWS Config Assessment Results",
                        "description": f"Automated evaluation results exported from AWS Config across {processed_files} files.", 
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
            
            # 4. Validate and Output
            assessment_results = ar.AssessmentResults.parse_obj(oscal_dict)
            output_file = output_dir / output_filename
            safe_json_string = assessment_results.json(exclude_none=True, by_alias=True)
            
            final_json = {
                "assessment-results": json.loads(safe_json_string)
            }
            
            with open(output_file, 'w') as f:
                json.dump(final_json, f, indent=2)

            logger.info(f"Successfully processed {processed_files} files and generated OSCAL file at {output_file}")
            return TaskOutcome.SUCCESS

        except Exception as e:
            logger.error(f"Error executing aws-config-to-oscal task: {e}")
            return TaskOutcome.FAILURE