import json
import os
from pathlib import Path

from trestle.tasks.aws_config_to_oscal import AwsConfigToOscal
from trestle.tasks.base_task import TaskOutcome

def test_aws_config_to_oscal_execute(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    input_file = input_dir / "aws_results.json"
    
    output_dir = tmp_path / "output"
    
    mock_aws_data = {
        "EvaluationResults": [
            {
                "EvaluationResultIdentifier": {
                    "EvaluationResultQualifier": {
                        "ConfigRuleName": "s3-bucket-public-read-prohibited",
                        "ResourceType": "AWS::S3::Bucket",
                        "ResourceId": "arn:aws:s3:::test-bucket"
                    }
                },
                "ComplianceType": "NON_COMPLIANT"
            }
        ]
    }
    
    with open(input_file, "w") as f:
        json.dump(mock_aws_data, f)
        
    # Testing our new dynamic configuration variables
    config = {
        "input-dir": str(input_dir),
        "output-dir": str(output_dir),
        "output-filename": "custom_aws_results.json",
        "metadata-title": "Custom AgStack Compliance Run",
        "assessment-plan-href": "fedramp-assessment-plan"
    }
    
    task = AwsConfigToOscal(config)
    outcome = task.execute()
    
    # Assert successful enum return
    assert outcome == TaskOutcome.SUCCESS
 
    output_file = output_dir / "custom_aws_results.json"
    assert output_file.exists()
    
    with open(output_file, "r") as f:
        oscal_data = json.load(f)
        
    # Verify the finding mapped correctly
    finding_state = oscal_data['assessment-results']['results'][0]['findings'][0]['target']['status']['state']
    assert finding_state == 'not-satisfied'
    
    # Verify dynamic metadata mapped correctly
    assert oscal_data['assessment-results']['metadata']['title'] == "Custom AgStack Compliance Run"
    assert oscal_data['assessment-results']['import-ap']['href'] == "fedramp-assessment-plan"