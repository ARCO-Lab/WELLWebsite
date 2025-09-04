# WELL Data Upload Instructions for Dataverse

## Overview
This document provides instructions for uploading data to the Dataverse repository for the WELL (Water Environment Learning Laboratory) project. **Please follow these instructions exactly** to ensure your data can be automatically processed by our system.

## File Format Requirements

### ⚠️ CRITICAL: Use the Sample File as Your Template
**You MUST use the exact same format as `WELLAncasterWatershed_SAMPLE.xlsx`**

- **Download the sample file**: `WELLAncasterWatershed_SAMPLE.xlsx` from the Dataverse repository
- **Copy this file** and modify it with your data
- **Do NOT create a new file from scratch** - always start with the sample file
- **Do NOT change the structure, column headers, or formatting** of the sample file

### File Format Specifications

1. **File Extension**: Must be `.xlsx` (Excel format)
   - ❌ NOT `.xls`, `.csv`, `.txt`, or any other format
   - ✅ Only `.xlsx` files will be processed

2. **Naming Convention**: `WELLAncasterWatershed_[description].xlsx`
   - **Required prefix**: `WELLAncasterWatershed_`
   - **Description**: Replace `[description]` with a meaningful identifier
   - **Examples**:
     - ✅ `WELLAncasterWatershed_January2024.xlsx`
     - ✅ `WELLAncasterWatershed_WinterSampling.xlsx`
     - ✅ `WELLAncasterWatershed_Site1_Q1.xlsx`
     - ❌ `lancaster_data.xlsx` (missing required prefix)
     - ❌ `WELLData_Jan.xlsx` (incorrect prefix)

## Step-by-Step Upload Process

### 1. Prepare Your Data File
1. Download `WELLAncasterWatershed_SAMPLE.xlsx` from the Dataverse
2. **Make a copy** of this file (do not edit the original sample)
3. Rename your copy following the naming convention: `WELLAncasterWatershed_[YourDescription].xlsx`
4. Replace the sample data with your actual data
5. **Keep all column headers, formatting, and structure exactly as shown in the sample**

### 2. Data Entry Guidelines
- **Do not add, remove, or rename columns**
- **Do not change the order of columns**
- **Follow the data format shown in the sample file**
- **Use the same units and formatting as the sample**
- **Leave cells blank if data is not available** (do not use "N/A", "NULL", etc.)

### 3. Upload to Dataverse
1. Log into the Dataverse repository
2. Navigate to the WELL dataset
3. Upload your `.xlsx` file
4. Verify the filename follows the `WELLAncasterWatershed_[description].xlsx` convention

## Important Reminders

### ✅ DO:
- Use `WELLAncasterWatershed_SAMPLE.xlsx` as your starting template
- Copy the sample file and modify it
- Keep the `.xlsx` format
- Follow the exact naming convention
- Preserve all column headers and structure
- Use meaningful descriptions in filenames

### ❌ DON'T:
- Create files from scratch
- Change column headers or structure
- Use any format other than `.xlsx`
- Use incorrect naming conventions
- Modify the sample file directly

## Troubleshooting

**Q: My file isn't being processed automatically**
- Check that your filename starts with `WELLAncasterWatershed_`
- Verify the file extension is `.xlsx`
- Ensure you used the sample file as your template

**Q: I need to add new types of measurements**
- Contact the WELL team before adding new columns
- The system expects the exact format from the sample file

**Q: Can I upload multiple files at once?**
- Yes, but each file must follow the naming convention individually
- Each file should contain a complete dataset for a specific time period or sampling event

## Contact Information

If you have questions about the upload format or encounter issues:
- Review the sample file: `WELLAncasterWatershed_SAMPLE.xlsx`
- Contact the WELL project team for assistance
- Check that you're following ALL requirements in this README

---

**Remember: When in doubt, always refer back to the sample file `WELLAncasterWatershed_SAMPLE.xlsx` and copy its exact format!**