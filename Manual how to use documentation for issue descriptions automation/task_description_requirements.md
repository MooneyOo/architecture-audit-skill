**JIRA Task Description Standard**

## **1. Title**

- **Purpose:** Provide a short, clear summary of the task.
    
- **Requirements:**
    
    - Be concise (ideally under 10 words).
        
    - Start with an action verb (e.g., _Implement_, _Configure_, _Create_, _Fix_).
        
    - Identify the area or feature affected (e.g., _Implement login validation for new users_).
        

## **2. Description**

- **Purpose:** Offer context and motivation for the task.
    
- **Requirements:**
    
    - Explain _what_ the task is and _why_ it’s needed.
        
    - Include background details (links to design docs, Confluence pages, or related tickets).
        
    - Describe the current state vs. desired outcome.
        
    - Optionally, provide screenshots or diagrams if UI or data flows are involved.
        

## **3. Requirements to Implement**

- **Purpose:** Define _what needs to be built or changed_ in specific, actionable terms.
    
- **Requirements:**
    
    - List functional and non-functional requirements.
        
    - Specify technical changes (e.g., database fields, API endpoints, logic rules).
        
    - Include dependencies or constraints (e.g., “requires backend endpoint to be available”).
        
    - Clarify environment or version details if relevant (e.g., “applies to mobile app v3.2+”).
        

## **4. Acceptance Criteria**

- **Purpose:** Define the conditions under which the task will be considered complete.
    
- **Requirements:**
    
    - Write criteria in **Given/When/Then** or **checklist** format.
        
    - Include measurable or testable outcomes (e.g., “User can reset password and receive confirmation email”).
        
    - Cover both positive and negative cases when relevant.
        
    - Ensure no ambiguity—criteria should be verifiable by testing or demonstration.
        

---

## **Example Template**

> **Title:** Implement password reset email for forgot password flow
> 
> **Description:**  
> Add email functionality for users requesting password resets. Currently, reset tokens are generated but emails aren’t sent. This feature ensures users receive reset instructions securely.
> 
> **Requirements to Implement:**
> 
> - Create email template using system mailer.
>     
> - Integrate with existing token generation logic.
>     
> - Add configuration option for SMTP sender in environment.
>     
> 
> **Acceptance Criteria:**
> 
> -  When a user requests a password reset, a valid link is sent to their email.
>     
> -  Link expires after 30 minutes.
>     
> -  Email logs are visible in admin dashboard.
>     