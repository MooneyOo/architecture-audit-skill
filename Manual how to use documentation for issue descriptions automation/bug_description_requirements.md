
**Bug Description Checklist for Jira**

There is a common checklist for creating bugs in Jira. Use it as recommendation and understand that there are specific rules or fields required for each project.

**Required fields to fill:**

- Summary
    
- Problem Description
    
- Environment
    
- Steps to Reproduce
    
- Actual Result
    
- Expected Result
    
- Priority
    
- Attachments if possible (.har file, screenshot, video)
    

**Optional fields to fill:**

- Severity
    
- Attachments
    
- Additional Information
    

### 1. **Summary**

- A concise title summarizing the issue.
    
    - Example: "[Login] Error message displayed when entering valid credentials"
        

### 2. **Problem Description**

- A detailed explanation of the issue, including:
    
    - The observed problem.
        
    - Where and when the problem occurs.
        
    - Any patterns or frequency of occurrence.
        
- Use clear and straightforward language.
    
    - Example: "When users attempt to log in with valid credentials, an error message is displayed stating 'Invalid username or password.' This occurs every time the login button is pressed."
        

### 3. **Environment**

- Provide specifics about where the bug was encountered:
    
    - Application version/build number.
        
    - Operating system (OS) version and type.
        
    - Browser type and version (if applicable).
        
    - Test environment (e.g., staging, production, QA).
        
    - Any other relevant configurations or devices.
        
    - Example: "Environment: Staging
        
        - Build: v1.2.3
            
        - OS: Windows 10, Version 21H2
            
        - Browser: Chrome v96.0"
            

### 4. **Steps to Reproduce**

- List the exact steps needed to replicate the issue:
    
    1. Navigate to the login page.
        
    2. Enter valid username and password.
        
    3. Click the login button.
        
- Ensure steps are sequential and reproducible by others.
    

### 5. **Actual Result**

- Describe what happens after performing the steps.
    
    - Include error messages, unexpected behaviors, or visuals.
        
    - Provide screenshots, screen recordings, or logs as attachments.
        
    - Example: "An error message appears: 'Invalid username or password.' Users cannot access their accounts."
        

### 6. **Expected Result**

- Define what should happen instead of the observed behavior.
    
    - Example: "The user should successfully log in and be redirected to the dashboard."
        

### 7. **Severity/Priority**

- **Severity:** Indicates the impact of the bug on the system’s functionality. It answers the question: "How bad is the bug?"
    
    - **Critical:** Prevents the system or a major feature from functioning.
        
    - **Major:** Affects primary functionality but the system remains operational.
        
    - **Minor:** Causes inconvenience but does not affect primary functionality.
        
    - **Trivial:** Cosmetic issues or minor annoyances.
        
- **Priority:** Determines the urgency for fixing the bug. It answers the question: "How soon should this be fixed?"
    
    - High, Medium, Low (if applicable in your workflow).
        

### 8. **Attachments**

- Add any supporting materials to aid in debugging:
    
    - Screenshots of the issue.
        
    - Video recordings showing the steps and bug.
        
    - Logs or console output (if applicable).
        
    - Example: "Screenshot attached showing the error message."
        
    - .har files from browser logs
        

### 9. **Additional Information**

- Include any additional notes that may help resolve the issue:
    
    - Whether the issue is intermittent or constant.
        
    - Any recent changes in the environment or code.
        
    - Related tickets (if any).
        
    - Example: "This issue started occurring after the recent deployment of build v1.2.3."
        

### Template Example

**Summary:** [Feature/Module] Brief description of the bug

**Problem Description:** Detailed explanation of the issue.

**Environment:**

- Build/Version: [Build Version]
    
- OS: [Operating System]
    
- Browser: [Browser]
    
- Environment: [Staging/Production/QA]
    

**Steps to Reproduce:**

1. [Step 1]
    
2. [Step 2]
    
3. [Step 3]
    

**Actual Result:** [Observed behavior with any error messages]

**Expected Result:** [Expected behavior]

**Severity:** [Severity Level]

**Priority:** [Priority Level]

**Attachments:** [List of attached files]

By following this checklist, your bug reports will provide developers with all necessary details, reducing back-and-forth communication and expediting the resolution process