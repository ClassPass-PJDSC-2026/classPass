# ClassPass Demo Script

**0:00–0:30 | The Problem**
**(Action: Start on the main app screen, sidebar visible)**

"Hello, we are the ClassPass team. Currently, school administrators have to choose between in-person, hybrid, or online classes without clear data on how airborne diseases like influenza will spread. Our tool, the Classroom Outbreak Simulator, solves this by providing a data-driven decision-support system to evaluate different safety measures."

**0:30–1:30 | Region Profile & Baseline KPIs**
**(Action: Show the sidebar. Briefly point mouse to Region and Class Size)**

"Let's look at how it works. We start by entering a school profile. For this demo, our values are fixed: a class size of 45 in a standard 9x7 meter room with 4 air changes per hour and no masks. 

**(Action: Click 'Run simulation' and switch to the Results tab)**

Once we run it, the dashboard gives us our baseline KPIs. We can see the attack rate, the peak infectious percentage, and the projected outbreak curve over 60 days."

**1:30–2:30 | Compare Scenarios & Trade-offs**
**(Action: Click the 'Compare' tab)**

"Next, we go to the Compare tab. Here, we can see the trade-offs. For example, we can compare our baseline against a hybrid learning scenario. While hybrid learning reduces infections, it increases the 'learner days lost'—which is a critical trade-off for school admins to see. We can also compare adding masks or better ventilation."

**2:30–3:30 | Sensitivity & Technical Rigor**
**(Action: Click the 'Sensitivity' tab)**

"To ensure technical rigor, we look at the Sensitivity tab. Because real-world data has uncertainty, we use a tornado chart to see how changing inputs, like the quanta rate, affects the outcome. The model couples a Wells-Riley airborne transmission model with an SEIR epidemiological framework. This ensures our recommendations are robust and hold up even when parameters vary."

**3:30–4:15 | Repo Tour**
**(Action: Switch to GitHub Tab 1: Code page)**

"Let's look at the code repository. Here is our directory structure: the `app` folder contains the Streamlit UI, `src` holds the core model, and `tests` contains our test suites. 

**(Action: Switch to GitHub Tab 2: Actions page)**

If we check the Actions tab, you can see our continuous integration pipeline is passing. We also have a validation notebook that checks our model against analytic values."

**4:15–4:45 | Limitations & Conclusion**
**(Action: Switch back to the Streamlit App)**

"To be fully transparent, our model assumes well-mixed air and uses synthetic data; it is a tool for comparing scenarios, not a medical forecasting device. We recommend expanding this to include Omicron-specific parameters in the future. 
ClassPass empowers schools to make safer, data-driven decisions. Thank you."