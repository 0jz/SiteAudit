from daytona import Daytona, DaytonaConfig

# Initialize Daytona
config = DaytonaConfig(api_key="dtn_94db53a48f46ec071b7bd5f2d288088285de2605b07c86728f284fb9839da3bf")
daytona = Daytona(config)
sandbox = daytona.create()

def run_in_sandbox(code: str) -> str:
    response = sandbox.process.code_run(code)
    if response.exit_code != 0:
        print(f"Error: {response.exit_code} {response.result}")
        return None
    return response.result

def invoke_lambda() -> str:
    code = """
import boto3, json
client = boto3.client('lambda', region_name='us-east-1')
response = client.invoke(FunctionName='your-function-name')
print(response['Payload'].read().decode())
"""
    return run_in_sandbox(code)

def call_claude(lambda_output: str):
    if not lambda_output:
        return
    code = f"""
import anthropic
client = anthropic.Anthropic()
message = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=4096,
    messages=[{{"role": "user", "content": {repr(lambda_output)}}}]
)
print(message.content[0].text)
"""
    result = run_in_sandbox(code)
    print(result)

# --- Triggers (pick one to run manually or wire to a scheduler) ---

def on_cloudwatch_alarm():
    """Trigger: aws.cloudwatch.onAlarm (state=ALARM, region=us-east-1)"""
    print("CloudWatch alarm fired")
    call_claude(invoke_lambda())

def on_schedule():
    """Trigger: schedule (every 1 day at 00:00)"""
    print("Scheduled trigger fired")
    call_claude(invoke_lambda())

def on_render_deploy():
    """Trigger: render.onDeploy (event=deploy_ended)"""
    print("Render deploy trigger fired")
    call_claude(invoke_lambda())


# --- Entry point ---
if __name__ == "__main__":
    # Swap this for whichever trigger you want to test
    on_schedule()
