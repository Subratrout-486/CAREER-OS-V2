from career_os.application.browser_runner import FormField, map_profile_fields


def test_maps_common_application_fields_without_model_calls():
    fields = [
        FormField(key="first", label="First Name", required=True),
        FormField(key="mail", label="Email address", required=True),
        FormField(key="unknown", label="Security clearance", required=True),
    ]
    profile = {"first_name": "Subrat", "email": "subrat@example.com"}

    mappings = map_profile_fields(fields, profile)

    assert mappings[0].value == "Subrat"
    assert mappings[0].confidence == 1.0
    assert mappings[1].value == "subrat@example.com"
    assert mappings[2].profile_key is None
    assert mappings[2].value is None


def test_unknown_questions_are_not_invented():
    fields = [FormField(key="q", label="Why do you want to work here?")]
    mappings = map_profile_fields(fields, {"email": "subrat@example.com"})

    assert mappings == [mappings[0]]
    assert mappings[0].profile_key is None
    assert mappings[0].value is None
    assert mappings[0].confidence == 0.0
