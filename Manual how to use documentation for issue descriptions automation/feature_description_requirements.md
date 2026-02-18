### **Example Epic: Lapsed Patient Report**

**Epic Title:** Lapsed Patient Report

**Epic Description:**  
This feature will generate an **automated daily report** of lapsed patients from the database and send it to a predefined group of recipients at each practice. The report will be delivered **at 9 AM CST daily**, ensuring that the practice team has updated patient data when the workday begins. To achieve this, the system must ensure that the **latest data from the practice management system (PMS) is pulled before report generation**.

#### **Definition of Done (DoD)**

- **Functional requirements:**
    
    - A report containing lapsed patients (patients who have not returned within a defined timeframe) is generated automatically every day.
        
    - The report is sent **at 9 AM CST** to a configurable list of email recipients.
        
    - The report includes key details such as **patient name, last visit date, last provider, and recommended follow-up actions**.
        
    - The system ensures that the latest data is pulled from the PMS before generating the report.
        
    - The list of recipient emails must be configurable per practice.
        
- **Edge cases:**
    
    - If data is not pulled from the PMS in time, the report should indicate that data is incomplete.
        
    - If there are no lapsed patients on a given day, the report should still be sent but state that no patients need follow-up.
        
    - If an email recipient is invalid or unreachable, the system should log an error but continue sending to the rest of the recipients.
        
    - If the PMS system is down or inaccessible, the system should retry fetching data within a reasonable timeframe before generating the report.
        
- **Acceptance criteria:**
    
    - The report is successfully generated and sent at **9 AM CST daily**.
        
    - Practices receive an email with the correct data, formatted according to specifications.
        
    - If PMS data is unavailable, the report clearly indicates missing data instead of failing silently.
        
    - All errors related to sending failures or missing data are logged for review.
        
    - The email recipient list can be **updated and managed per practice** via a configuration interface.
        
- **Testing requirements:**
    
    - Verify that reports are generated and sent correctly at 9 AM CST.
        
    - Test with **real PMS data** to ensure accuracy.
        
    - Simulate PMS downtime to validate retry mechanisms and fallback handling.
        
    - Confirm that invalid emails do not block report delivery to valid recipients.
        
    - Validate report format and email layout for usability.
        

#### **Dependencies**

- PMS integration must be functional and capable of retrieving lapsed patient data before 9 AM CST.
    
- Email service must be configured and tested for automated daily report delivery.
    
- Practices must have their email recipient lists set up before activation of the feature.