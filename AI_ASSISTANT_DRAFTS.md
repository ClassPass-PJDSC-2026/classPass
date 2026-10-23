# AI Assistant: Mass-Communication Drafts (#25)

## Purpose
To provide automated, clear, and actionable communication to users regarding their simulation results, system updates, and alerts.

## Draft 1: Welcome / Onboarding Message
**Prompt / Context:** Triggered when a new user logs in or creates an account.

**Draft Text:** 
"Welcome to ClassPass! I'm your AI assistant. To get started, please upload your `params.yaml` file or adjust the scenario settings on the left. I'll be here to help you read the results and sensitivity charts once the simulation runs."

## Draft 2: Reminder / Notification
**Prompt / Context:** Triggered if the simulation takes longer than expected.

**Draft Text:** 
"Just a heads up: The sensitivity analysis is running a large number of scenarios. This might take a few moments. You can still view your previous Results tab while this computes in the background."

## Draft 3: Issue / Alert
**Prompt / Context:** Triggered if there is an error in the parameter file.

**Draft Text:** 
"Alert: I noticed an issue with your parameter inputs. The 'attack_rate' value is missing or out of range. Please check your `params.yaml` file and try again."