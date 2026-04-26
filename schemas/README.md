# Import Schemas

This folder contains JSON Schemas used to validate CSV import content.

## Files

- `roster.json` - Validates student roster columns and constraints.
- `timetable.json` - Validates timetable structure and period headers.
- `teachers.json` - Validates subject-to-teacher mapping format.

## How It Is Used

- Backend import endpoints apply these schemas before writing data.
- Validation is strict and import is rejected when any row fails.

## Related

- Rules and behavior details: `import/README.md`
- Example CSV input files: `samples/`
