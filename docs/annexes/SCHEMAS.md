# Annexe B : schémas JSON des entrées et sorties

Fichier généré par `scripts/generate_docs_annexes.py` (Pydantic `model_json_schema`).
Toutes les sorties utilisent `extra="forbid"` : un champ inattendu est rejeté.

## Agent 1

### Entrée : `JobRequirementInput`

```json
{
  "properties": {
    "title": {
      "maxLength": 300,
      "minLength": 1,
      "title": "Title",
      "type": "string"
    },
    "description": {
      "default": "",
      "maxLength": 10000,
      "title": "Description",
      "type": "string"
    },
    "required_degree": {
      "default": "",
      "maxLength": 300,
      "title": "Required Degree",
      "type": "string"
    },
    "minimum_experience_years": {
      "anyOf": [
        {
          "maximum": 80.0,
          "minimum": 0.0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Minimum Experience Years"
    },
    "required_skills": {
      "items": {
        "type": "string"
      },
      "maxItems": 100,
      "title": "Required Skills",
      "type": "array"
    },
    "preferred_skills": {
      "items": {
        "type": "string"
      },
      "maxItems": 100,
      "title": "Preferred Skills",
      "type": "array"
    },
    "required_certifications": {
      "items": {
        "type": "string"
      },
      "maxItems": 50,
      "title": "Required Certifications",
      "type": "array"
    },
    "languages": {
      "items": {
        "type": "string"
      },
      "maxItems": 30,
      "title": "Languages",
      "type": "array"
    },
    "other_requirements": {
      "default": "",
      "maxLength": 5000,
      "title": "Other Requirements",
      "type": "string"
    }
  },
  "required": [
    "title"
  ],
  "title": "JobRequirementInput",
  "type": "object"
}
```

### Sortie : `StructuredRequirementsOut`

```json
{
  "additionalProperties": false,
  "properties": {
    "required_degree": {
      "default": "",
      "maxLength": 300,
      "title": "Required Degree",
      "type": "string"
    },
    "minimum_experience_years": {
      "default": 0,
      "maximum": 80.0,
      "minimum": 0.0,
      "title": "Minimum Experience Years",
      "type": "number"
    },
    "required_skills": {
      "items": {
        "type": "string"
      },
      "maxItems": 100,
      "title": "Required Skills",
      "type": "array"
    },
    "preferred_skills": {
      "items": {
        "type": "string"
      },
      "maxItems": 100,
      "title": "Preferred Skills",
      "type": "array"
    },
    "required_certifications": {
      "items": {
        "type": "string"
      },
      "maxItems": 50,
      "title": "Required Certifications",
      "type": "array"
    },
    "languages": {
      "items": {
        "type": "string"
      },
      "maxItems": 30,
      "title": "Languages",
      "type": "array"
    },
    "other_requirements": {
      "default": "",
      "maxLength": 5000,
      "title": "Other Requirements",
      "type": "string"
    }
  },
  "title": "StructuredRequirementsOut",
  "type": "object"
}
```

## Agent 2

### Entrée : `CVExtractionInput`

```json
{
  "properties": {
    "cv_text": {
      "maxLength": 100000,
      "minLength": 1,
      "title": "Cv Text",
      "type": "string"
    }
  },
  "required": [
    "cv_text"
  ],
  "title": "CVExtractionInput",
  "type": "object"
}
```

### Sortie : `ExtractedProfileOut`

```json
{
  "$defs": {
    "DeclaredIdentityOut": {
      "additionalProperties": false,
      "properties": {
        "first_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "First Name"
        },
        "last_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Name"
        },
        "birth_date": {
          "anyOf": [
            {
              "format": "date",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Birth Date"
        }
      },
      "title": "DeclaredIdentityOut",
      "type": "object"
    },
    "ExperienceOut": {
      "additionalProperties": false,
      "properties": {
        "position": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Position",
          "type": "string"
        },
        "employer": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Employer",
          "type": "string"
        },
        "duration_months": {
          "maximum": 960,
          "minimum": 0,
          "title": "Duration Months",
          "type": "integer"
        }
      },
      "required": [
        "position",
        "employer",
        "duration_months"
      ],
      "title": "ExperienceOut",
      "type": "object"
    },
    "ProjectOut": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "description": {
          "default": "",
          "maxLength": 1000,
          "title": "Description",
          "type": "string"
        },
        "technologies": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Technologies",
          "type": "array"
        }
      },
      "required": [
        "name"
      ],
      "title": "ProjectOut",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "education": {
      "items": {
        "type": "string"
      },
      "maxItems": 50,
      "title": "Education",
      "type": "array"
    },
    "diplomas": {
      "items": {
        "type": "string"
      },
      "maxItems": 50,
      "title": "Diplomas",
      "type": "array"
    },
    "experiences": {
      "items": {
        "$ref": "#/$defs/ExperienceOut"
      },
      "maxItems": 50,
      "title": "Experiences",
      "type": "array"
    },
    "projects": {
      "items": {
        "$ref": "#/$defs/ProjectOut"
      },
      "maxItems": 50,
      "title": "Projects",
      "type": "array"
    },
    "skills": {
      "items": {
        "type": "string"
      },
      "maxItems": 100,
      "title": "Skills",
      "type": "array"
    },
    "certifications": {
      "items": {
        "type": "string"
      },
      "maxItems": 50,
      "title": "Certifications",
      "type": "array"
    },
    "professional_contributions": {
      "items": {
        "type": "string"
      },
      "maxItems": 50,
      "title": "Professional Contributions",
      "type": "array"
    },
    "languages": {
      "items": {
        "type": "string"
      },
      "maxItems": 30,
      "title": "Languages",
      "type": "array"
    },
    "declared_identity": {
      "$ref": "#/$defs/DeclaredIdentityOut"
    }
  },
  "title": "ExtractedProfileOut",
  "type": "object"
}
```

## Agent 3 (extraction LLM)

### Entrée : `DocumentVerificationInput`

```json
{
  "$defs": {
    "DeclaredIdentityOut": {
      "additionalProperties": false,
      "properties": {
        "first_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "First Name"
        },
        "last_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Name"
        },
        "birth_date": {
          "anyOf": [
            {
              "format": "date",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Birth Date"
        }
      },
      "title": "DeclaredIdentityOut",
      "type": "object"
    },
    "ExperienceOut": {
      "additionalProperties": false,
      "properties": {
        "position": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Position",
          "type": "string"
        },
        "employer": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Employer",
          "type": "string"
        },
        "duration_months": {
          "maximum": 960,
          "minimum": 0,
          "title": "Duration Months",
          "type": "integer"
        }
      },
      "required": [
        "position",
        "employer",
        "duration_months"
      ],
      "title": "ExperienceOut",
      "type": "object"
    },
    "ExtractedProfileOut": {
      "additionalProperties": false,
      "properties": {
        "education": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Education",
          "type": "array"
        },
        "diplomas": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Diplomas",
          "type": "array"
        },
        "experiences": {
          "items": {
            "$ref": "#/$defs/ExperienceOut"
          },
          "maxItems": 50,
          "title": "Experiences",
          "type": "array"
        },
        "projects": {
          "items": {
            "$ref": "#/$defs/ProjectOut"
          },
          "maxItems": 50,
          "title": "Projects",
          "type": "array"
        },
        "skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Skills",
          "type": "array"
        },
        "certifications": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Certifications",
          "type": "array"
        },
        "professional_contributions": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Professional Contributions",
          "type": "array"
        },
        "languages": {
          "items": {
            "type": "string"
          },
          "maxItems": 30,
          "title": "Languages",
          "type": "array"
        },
        "declared_identity": {
          "$ref": "#/$defs/DeclaredIdentityOut"
        }
      },
      "title": "ExtractedProfileOut",
      "type": "object"
    },
    "ProjectOut": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "description": {
          "default": "",
          "maxLength": 1000,
          "title": "Description",
          "type": "string"
        },
        "technologies": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Technologies",
          "type": "array"
        }
      },
      "required": [
        "name"
      ],
      "title": "ProjectOut",
      "type": "object"
    }
  },
  "properties": {
    "diploma_text": {
      "anyOf": [
        {
          "maxLength": 100000,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Diploma Text"
    },
    "cin_text": {
      "anyOf": [
        {
          "maxLength": 100000,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Cin Text"
    },
    "cv_profile": {
      "$ref": "#/$defs/ExtractedProfileOut"
    },
    "diploma_read_error": {
      "anyOf": [
        {
          "maxLength": 300,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Diploma Read Error"
    },
    "cin_read_error": {
      "anyOf": [
        {
          "maxLength": 300,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Cin Read Error"
    }
  },
  "required": [
    "cv_profile"
  ],
  "title": "DocumentVerificationInput",
  "type": "object"
}
```

### Sortie : `VerificationExtractionOut`

```json
{
  "properties": {
    "first_name": {
      "anyOf": [
        {
          "maxLength": 100,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "First Name"
    },
    "last_name": {
      "anyOf": [
        {
          "maxLength": 100,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Last Name"
    },
    "birth_date": {
      "anyOf": [
        {
          "maxLength": 30,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Birth Date"
    },
    "cin_number": {
      "anyOf": [
        {
          "maxLength": 100,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Cin Number"
    },
    "diploma_holder_first_name": {
      "anyOf": [
        {
          "maxLength": 100,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Diploma Holder First Name"
    },
    "diploma_holder_last_name": {
      "anyOf": [
        {
          "maxLength": 100,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Diploma Holder Last Name"
    },
    "diploma_title": {
      "anyOf": [
        {
          "maxLength": 300,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Diploma Title"
    },
    "institution": {
      "anyOf": [
        {
          "maxLength": 300,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Institution"
    },
    "graduation_year": {
      "anyOf": [
        {
          "maximum": 2100,
          "minimum": 1900,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Graduation Year"
    }
  },
  "title": "VerificationExtractionOut",
  "type": "object"
}
```

## Agent 3 (sortie finale)

### Entrée : `DocumentVerificationInput`

```json
{
  "$defs": {
    "DeclaredIdentityOut": {
      "additionalProperties": false,
      "properties": {
        "first_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "First Name"
        },
        "last_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Name"
        },
        "birth_date": {
          "anyOf": [
            {
              "format": "date",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Birth Date"
        }
      },
      "title": "DeclaredIdentityOut",
      "type": "object"
    },
    "ExperienceOut": {
      "additionalProperties": false,
      "properties": {
        "position": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Position",
          "type": "string"
        },
        "employer": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Employer",
          "type": "string"
        },
        "duration_months": {
          "maximum": 960,
          "minimum": 0,
          "title": "Duration Months",
          "type": "integer"
        }
      },
      "required": [
        "position",
        "employer",
        "duration_months"
      ],
      "title": "ExperienceOut",
      "type": "object"
    },
    "ExtractedProfileOut": {
      "additionalProperties": false,
      "properties": {
        "education": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Education",
          "type": "array"
        },
        "diplomas": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Diplomas",
          "type": "array"
        },
        "experiences": {
          "items": {
            "$ref": "#/$defs/ExperienceOut"
          },
          "maxItems": 50,
          "title": "Experiences",
          "type": "array"
        },
        "projects": {
          "items": {
            "$ref": "#/$defs/ProjectOut"
          },
          "maxItems": 50,
          "title": "Projects",
          "type": "array"
        },
        "skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Skills",
          "type": "array"
        },
        "certifications": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Certifications",
          "type": "array"
        },
        "professional_contributions": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Professional Contributions",
          "type": "array"
        },
        "languages": {
          "items": {
            "type": "string"
          },
          "maxItems": 30,
          "title": "Languages",
          "type": "array"
        },
        "declared_identity": {
          "$ref": "#/$defs/DeclaredIdentityOut"
        }
      },
      "title": "ExtractedProfileOut",
      "type": "object"
    },
    "ProjectOut": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "description": {
          "default": "",
          "maxLength": 1000,
          "title": "Description",
          "type": "string"
        },
        "technologies": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Technologies",
          "type": "array"
        }
      },
      "required": [
        "name"
      ],
      "title": "ProjectOut",
      "type": "object"
    }
  },
  "properties": {
    "diploma_text": {
      "anyOf": [
        {
          "maxLength": 100000,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Diploma Text"
    },
    "cin_text": {
      "anyOf": [
        {
          "maxLength": 100000,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Cin Text"
    },
    "cv_profile": {
      "$ref": "#/$defs/ExtractedProfileOut"
    },
    "diploma_read_error": {
      "anyOf": [
        {
          "maxLength": 300,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Diploma Read Error"
    },
    "cin_read_error": {
      "anyOf": [
        {
          "maxLength": 300,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Cin Read Error"
    }
  },
  "required": [
    "cv_profile"
  ],
  "title": "DocumentVerificationInput",
  "type": "object"
}
```

### Sortie : `DocumentVerificationOut`

```json
{
  "$defs": {
    "InconsistencyOut": {
      "additionalProperties": false,
      "properties": {
        "field": {
          "maxLength": 100,
          "minLength": 1,
          "title": "Field",
          "type": "string"
        },
        "cv_value": {
          "maxLength": 500,
          "title": "Cv Value",
          "type": "string"
        },
        "document_value": {
          "maxLength": 500,
          "title": "Document Value",
          "type": "string"
        },
        "severity": {
          "enum": [
            "low",
            "medium",
            "high"
          ],
          "title": "Severity",
          "type": "string"
        },
        "kind": {
          "default": "identity",
          "enum": [
            "identity",
            "diploma_holder",
            "diploma_title",
            "year",
            "institution",
            "missing",
            "unreadable"
          ],
          "title": "Kind",
          "type": "string"
        },
        "explanation": {
          "default": "",
          "maxLength": 500,
          "title": "Explanation",
          "type": "string"
        }
      },
      "required": [
        "field",
        "cv_value",
        "document_value",
        "severity"
      ],
      "title": "InconsistencyOut",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "diploma_info": {
      "additionalProperties": {
        "type": "string"
      },
      "maxProperties": 30,
      "title": "Diploma Info",
      "type": "object"
    },
    "cin_info": {
      "additionalProperties": {
        "type": "string"
      },
      "maxProperties": 30,
      "title": "Cin Info",
      "type": "object"
    },
    "inconsistencies": {
      "items": {
        "$ref": "#/$defs/InconsistencyOut"
      },
      "maxItems": 100,
      "title": "Inconsistencies",
      "type": "array"
    },
    "compliance_level": {
      "maximum": 100.0,
      "minimum": 0.0,
      "title": "Compliance Level",
      "type": "number"
    }
  },
  "required": [
    "compliance_level"
  ],
  "title": "DocumentVerificationOut",
  "type": "object"
}
```

## Agent 4 (réponse LLM)

### Entrée : `MatchingInput`

```json
{
  "$defs": {
    "DeclaredIdentityOut": {
      "additionalProperties": false,
      "properties": {
        "first_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "First Name"
        },
        "last_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Name"
        },
        "birth_date": {
          "anyOf": [
            {
              "format": "date",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Birth Date"
        }
      },
      "title": "DeclaredIdentityOut",
      "type": "object"
    },
    "DocumentVerificationOut": {
      "additionalProperties": false,
      "properties": {
        "diploma_info": {
          "additionalProperties": {
            "type": "string"
          },
          "maxProperties": 30,
          "title": "Diploma Info",
          "type": "object"
        },
        "cin_info": {
          "additionalProperties": {
            "type": "string"
          },
          "maxProperties": 30,
          "title": "Cin Info",
          "type": "object"
        },
        "inconsistencies": {
          "items": {
            "$ref": "#/$defs/InconsistencyOut"
          },
          "maxItems": 100,
          "title": "Inconsistencies",
          "type": "array"
        },
        "compliance_level": {
          "maximum": 100.0,
          "minimum": 0.0,
          "title": "Compliance Level",
          "type": "number"
        }
      },
      "required": [
        "compliance_level"
      ],
      "title": "DocumentVerificationOut",
      "type": "object"
    },
    "ExperienceOut": {
      "additionalProperties": false,
      "properties": {
        "position": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Position",
          "type": "string"
        },
        "employer": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Employer",
          "type": "string"
        },
        "duration_months": {
          "maximum": 960,
          "minimum": 0,
          "title": "Duration Months",
          "type": "integer"
        }
      },
      "required": [
        "position",
        "employer",
        "duration_months"
      ],
      "title": "ExperienceOut",
      "type": "object"
    },
    "ExtractedProfileOut": {
      "additionalProperties": false,
      "properties": {
        "education": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Education",
          "type": "array"
        },
        "diplomas": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Diplomas",
          "type": "array"
        },
        "experiences": {
          "items": {
            "$ref": "#/$defs/ExperienceOut"
          },
          "maxItems": 50,
          "title": "Experiences",
          "type": "array"
        },
        "projects": {
          "items": {
            "$ref": "#/$defs/ProjectOut"
          },
          "maxItems": 50,
          "title": "Projects",
          "type": "array"
        },
        "skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Skills",
          "type": "array"
        },
        "certifications": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Certifications",
          "type": "array"
        },
        "professional_contributions": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Professional Contributions",
          "type": "array"
        },
        "languages": {
          "items": {
            "type": "string"
          },
          "maxItems": 30,
          "title": "Languages",
          "type": "array"
        },
        "declared_identity": {
          "$ref": "#/$defs/DeclaredIdentityOut"
        }
      },
      "title": "ExtractedProfileOut",
      "type": "object"
    },
    "InconsistencyOut": {
      "additionalProperties": false,
      "properties": {
        "field": {
          "maxLength": 100,
          "minLength": 1,
          "title": "Field",
          "type": "string"
        },
        "cv_value": {
          "maxLength": 500,
          "title": "Cv Value",
          "type": "string"
        },
        "document_value": {
          "maxLength": 500,
          "title": "Document Value",
          "type": "string"
        },
        "severity": {
          "enum": [
            "low",
            "medium",
            "high"
          ],
          "title": "Severity",
          "type": "string"
        },
        "kind": {
          "default": "identity",
          "enum": [
            "identity",
            "diploma_holder",
            "diploma_title",
            "year",
            "institution",
            "missing",
            "unreadable"
          ],
          "title": "Kind",
          "type": "string"
        },
        "explanation": {
          "default": "",
          "maxLength": 500,
          "title": "Explanation",
          "type": "string"
        }
      },
      "required": [
        "field",
        "cv_value",
        "document_value",
        "severity"
      ],
      "title": "InconsistencyOut",
      "type": "object"
    },
    "ProjectOut": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "description": {
          "default": "",
          "maxLength": 1000,
          "title": "Description",
          "type": "string"
        },
        "technologies": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Technologies",
          "type": "array"
        }
      },
      "required": [
        "name"
      ],
      "title": "ProjectOut",
      "type": "object"
    },
    "StructuredRequirementsOut": {
      "additionalProperties": false,
      "properties": {
        "required_degree": {
          "default": "",
          "maxLength": 300,
          "title": "Required Degree",
          "type": "string"
        },
        "minimum_experience_years": {
          "default": 0,
          "maximum": 80.0,
          "minimum": 0.0,
          "title": "Minimum Experience Years",
          "type": "number"
        },
        "required_skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Required Skills",
          "type": "array"
        },
        "preferred_skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Preferred Skills",
          "type": "array"
        },
        "required_certifications": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Required Certifications",
          "type": "array"
        },
        "languages": {
          "items": {
            "type": "string"
          },
          "maxItems": 30,
          "title": "Languages",
          "type": "array"
        },
        "other_requirements": {
          "default": "",
          "maxLength": 5000,
          "title": "Other Requirements",
          "type": "string"
        }
      },
      "title": "StructuredRequirementsOut",
      "type": "object"
    }
  },
  "properties": {
    "requirements": {
      "$ref": "#/$defs/StructuredRequirementsOut"
    },
    "profile": {
      "$ref": "#/$defs/ExtractedProfileOut"
    },
    "document_verification": {
      "$ref": "#/$defs/DocumentVerificationOut"
    }
  },
  "required": [
    "requirements",
    "profile",
    "document_verification"
  ],
  "title": "MatchingInput",
  "type": "object"
}
```

### Sortie : `SemanticEvaluationOut`

```json
{
  "$defs": {
    "SemanticCriterionOut": {
      "properties": {
        "name": {
          "maxLength": 150,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "verdict": {
          "enum": [
            "match",
            "partiel",
            "absent"
          ],
          "title": "Verdict",
          "type": "string"
        },
        "justification": {
          "default": "",
          "maxLength": 1000,
          "title": "Justification",
          "type": "string"
        },
        "evidence": {
          "items": {
            "type": "string"
          },
          "maxItems": 10,
          "title": "Evidence",
          "type": "array"
        }
      },
      "required": [
        "name",
        "verdict"
      ],
      "title": "SemanticCriterionOut",
      "type": "object"
    }
  },
  "properties": {
    "criteria": {
      "items": {
        "$ref": "#/$defs/SemanticCriterionOut"
      },
      "maxItems": 200,
      "title": "Criteria",
      "type": "array"
    }
  },
  "title": "SemanticEvaluationOut",
  "type": "object"
}
```

## Agent 4 (sortie finale)

### Entrée : `MatchingInput`

```json
{
  "$defs": {
    "DeclaredIdentityOut": {
      "additionalProperties": false,
      "properties": {
        "first_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "First Name"
        },
        "last_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Name"
        },
        "birth_date": {
          "anyOf": [
            {
              "format": "date",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Birth Date"
        }
      },
      "title": "DeclaredIdentityOut",
      "type": "object"
    },
    "DocumentVerificationOut": {
      "additionalProperties": false,
      "properties": {
        "diploma_info": {
          "additionalProperties": {
            "type": "string"
          },
          "maxProperties": 30,
          "title": "Diploma Info",
          "type": "object"
        },
        "cin_info": {
          "additionalProperties": {
            "type": "string"
          },
          "maxProperties": 30,
          "title": "Cin Info",
          "type": "object"
        },
        "inconsistencies": {
          "items": {
            "$ref": "#/$defs/InconsistencyOut"
          },
          "maxItems": 100,
          "title": "Inconsistencies",
          "type": "array"
        },
        "compliance_level": {
          "maximum": 100.0,
          "minimum": 0.0,
          "title": "Compliance Level",
          "type": "number"
        }
      },
      "required": [
        "compliance_level"
      ],
      "title": "DocumentVerificationOut",
      "type": "object"
    },
    "ExperienceOut": {
      "additionalProperties": false,
      "properties": {
        "position": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Position",
          "type": "string"
        },
        "employer": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Employer",
          "type": "string"
        },
        "duration_months": {
          "maximum": 960,
          "minimum": 0,
          "title": "Duration Months",
          "type": "integer"
        }
      },
      "required": [
        "position",
        "employer",
        "duration_months"
      ],
      "title": "ExperienceOut",
      "type": "object"
    },
    "ExtractedProfileOut": {
      "additionalProperties": false,
      "properties": {
        "education": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Education",
          "type": "array"
        },
        "diplomas": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Diplomas",
          "type": "array"
        },
        "experiences": {
          "items": {
            "$ref": "#/$defs/ExperienceOut"
          },
          "maxItems": 50,
          "title": "Experiences",
          "type": "array"
        },
        "projects": {
          "items": {
            "$ref": "#/$defs/ProjectOut"
          },
          "maxItems": 50,
          "title": "Projects",
          "type": "array"
        },
        "skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Skills",
          "type": "array"
        },
        "certifications": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Certifications",
          "type": "array"
        },
        "professional_contributions": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Professional Contributions",
          "type": "array"
        },
        "languages": {
          "items": {
            "type": "string"
          },
          "maxItems": 30,
          "title": "Languages",
          "type": "array"
        },
        "declared_identity": {
          "$ref": "#/$defs/DeclaredIdentityOut"
        }
      },
      "title": "ExtractedProfileOut",
      "type": "object"
    },
    "InconsistencyOut": {
      "additionalProperties": false,
      "properties": {
        "field": {
          "maxLength": 100,
          "minLength": 1,
          "title": "Field",
          "type": "string"
        },
        "cv_value": {
          "maxLength": 500,
          "title": "Cv Value",
          "type": "string"
        },
        "document_value": {
          "maxLength": 500,
          "title": "Document Value",
          "type": "string"
        },
        "severity": {
          "enum": [
            "low",
            "medium",
            "high"
          ],
          "title": "Severity",
          "type": "string"
        },
        "kind": {
          "default": "identity",
          "enum": [
            "identity",
            "diploma_holder",
            "diploma_title",
            "year",
            "institution",
            "missing",
            "unreadable"
          ],
          "title": "Kind",
          "type": "string"
        },
        "explanation": {
          "default": "",
          "maxLength": 500,
          "title": "Explanation",
          "type": "string"
        }
      },
      "required": [
        "field",
        "cv_value",
        "document_value",
        "severity"
      ],
      "title": "InconsistencyOut",
      "type": "object"
    },
    "ProjectOut": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "description": {
          "default": "",
          "maxLength": 1000,
          "title": "Description",
          "type": "string"
        },
        "technologies": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Technologies",
          "type": "array"
        }
      },
      "required": [
        "name"
      ],
      "title": "ProjectOut",
      "type": "object"
    },
    "StructuredRequirementsOut": {
      "additionalProperties": false,
      "properties": {
        "required_degree": {
          "default": "",
          "maxLength": 300,
          "title": "Required Degree",
          "type": "string"
        },
        "minimum_experience_years": {
          "default": 0,
          "maximum": 80.0,
          "minimum": 0.0,
          "title": "Minimum Experience Years",
          "type": "number"
        },
        "required_skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Required Skills",
          "type": "array"
        },
        "preferred_skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Preferred Skills",
          "type": "array"
        },
        "required_certifications": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Required Certifications",
          "type": "array"
        },
        "languages": {
          "items": {
            "type": "string"
          },
          "maxItems": 30,
          "title": "Languages",
          "type": "array"
        },
        "other_requirements": {
          "default": "",
          "maxLength": 5000,
          "title": "Other Requirements",
          "type": "string"
        }
      },
      "title": "StructuredRequirementsOut",
      "type": "object"
    }
  },
  "properties": {
    "requirements": {
      "$ref": "#/$defs/StructuredRequirementsOut"
    },
    "profile": {
      "$ref": "#/$defs/ExtractedProfileOut"
    },
    "document_verification": {
      "$ref": "#/$defs/DocumentVerificationOut"
    }
  },
  "required": [
    "requirements",
    "profile",
    "document_verification"
  ],
  "title": "MatchingInput",
  "type": "object"
}
```

### Sortie : `MatchingOut`

```json
{
  "$defs": {
    "MatchingCriterionOut": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 100,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "score": {
          "maximum": 100.0,
          "minimum": 0.0,
          "title": "Score",
          "type": "number"
        },
        "weight": {
          "maximum": 100.0,
          "minimum": 0.0,
          "title": "Weight",
          "type": "number"
        },
        "justification": {
          "maxLength": 1000,
          "minLength": 1,
          "title": "Justification",
          "type": "string"
        },
        "evidence": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Evidence",
          "type": "array"
        }
      },
      "required": [
        "name",
        "score",
        "weight",
        "justification"
      ],
      "title": "MatchingCriterionOut",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "global_score": {
      "maximum": 100.0,
      "minimum": 0.0,
      "title": "Global Score",
      "type": "number"
    },
    "criteria": {
      "items": {
        "$ref": "#/$defs/MatchingCriterionOut"
      },
      "maxItems": 50,
      "title": "Criteria",
      "type": "array"
    },
    "matching_skills": {
      "items": {
        "type": "string"
      },
      "maxItems": 100,
      "title": "Matching Skills",
      "type": "array"
    },
    "missing_skills": {
      "items": {
        "type": "string"
      },
      "maxItems": 100,
      "title": "Missing Skills",
      "type": "array"
    }
  },
  "required": [
    "global_score"
  ],
  "title": "MatchingOut",
  "type": "object"
}
```

## Agent 5

### Entrée : `ReportInput`

```json
{
  "$defs": {
    "DeclaredIdentityOut": {
      "additionalProperties": false,
      "properties": {
        "first_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "First Name"
        },
        "last_name": {
          "anyOf": [
            {
              "maxLength": 100,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Name"
        },
        "birth_date": {
          "anyOf": [
            {
              "format": "date",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Birth Date"
        }
      },
      "title": "DeclaredIdentityOut",
      "type": "object"
    },
    "DocumentVerificationOut": {
      "additionalProperties": false,
      "properties": {
        "diploma_info": {
          "additionalProperties": {
            "type": "string"
          },
          "maxProperties": 30,
          "title": "Diploma Info",
          "type": "object"
        },
        "cin_info": {
          "additionalProperties": {
            "type": "string"
          },
          "maxProperties": 30,
          "title": "Cin Info",
          "type": "object"
        },
        "inconsistencies": {
          "items": {
            "$ref": "#/$defs/InconsistencyOut"
          },
          "maxItems": 100,
          "title": "Inconsistencies",
          "type": "array"
        },
        "compliance_level": {
          "maximum": 100.0,
          "minimum": 0.0,
          "title": "Compliance Level",
          "type": "number"
        }
      },
      "required": [
        "compliance_level"
      ],
      "title": "DocumentVerificationOut",
      "type": "object"
    },
    "ExperienceOut": {
      "additionalProperties": false,
      "properties": {
        "position": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Position",
          "type": "string"
        },
        "employer": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Employer",
          "type": "string"
        },
        "duration_months": {
          "maximum": 960,
          "minimum": 0,
          "title": "Duration Months",
          "type": "integer"
        }
      },
      "required": [
        "position",
        "employer",
        "duration_months"
      ],
      "title": "ExperienceOut",
      "type": "object"
    },
    "ExtractedProfileOut": {
      "additionalProperties": false,
      "properties": {
        "education": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Education",
          "type": "array"
        },
        "diplomas": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Diplomas",
          "type": "array"
        },
        "experiences": {
          "items": {
            "$ref": "#/$defs/ExperienceOut"
          },
          "maxItems": 50,
          "title": "Experiences",
          "type": "array"
        },
        "projects": {
          "items": {
            "$ref": "#/$defs/ProjectOut"
          },
          "maxItems": 50,
          "title": "Projects",
          "type": "array"
        },
        "skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Skills",
          "type": "array"
        },
        "certifications": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Certifications",
          "type": "array"
        },
        "professional_contributions": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Professional Contributions",
          "type": "array"
        },
        "languages": {
          "items": {
            "type": "string"
          },
          "maxItems": 30,
          "title": "Languages",
          "type": "array"
        },
        "declared_identity": {
          "$ref": "#/$defs/DeclaredIdentityOut"
        }
      },
      "title": "ExtractedProfileOut",
      "type": "object"
    },
    "InconsistencyOut": {
      "additionalProperties": false,
      "properties": {
        "field": {
          "maxLength": 100,
          "minLength": 1,
          "title": "Field",
          "type": "string"
        },
        "cv_value": {
          "maxLength": 500,
          "title": "Cv Value",
          "type": "string"
        },
        "document_value": {
          "maxLength": 500,
          "title": "Document Value",
          "type": "string"
        },
        "severity": {
          "enum": [
            "low",
            "medium",
            "high"
          ],
          "title": "Severity",
          "type": "string"
        },
        "kind": {
          "default": "identity",
          "enum": [
            "identity",
            "diploma_holder",
            "diploma_title",
            "year",
            "institution",
            "missing",
            "unreadable"
          ],
          "title": "Kind",
          "type": "string"
        },
        "explanation": {
          "default": "",
          "maxLength": 500,
          "title": "Explanation",
          "type": "string"
        }
      },
      "required": [
        "field",
        "cv_value",
        "document_value",
        "severity"
      ],
      "title": "InconsistencyOut",
      "type": "object"
    },
    "MatchingCriterionOut": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 100,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "score": {
          "maximum": 100.0,
          "minimum": 0.0,
          "title": "Score",
          "type": "number"
        },
        "weight": {
          "maximum": 100.0,
          "minimum": 0.0,
          "title": "Weight",
          "type": "number"
        },
        "justification": {
          "maxLength": 1000,
          "minLength": 1,
          "title": "Justification",
          "type": "string"
        },
        "evidence": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Evidence",
          "type": "array"
        }
      },
      "required": [
        "name",
        "score",
        "weight",
        "justification"
      ],
      "title": "MatchingCriterionOut",
      "type": "object"
    },
    "MatchingOut": {
      "additionalProperties": false,
      "properties": {
        "global_score": {
          "maximum": 100.0,
          "minimum": 0.0,
          "title": "Global Score",
          "type": "number"
        },
        "criteria": {
          "items": {
            "$ref": "#/$defs/MatchingCriterionOut"
          },
          "maxItems": 50,
          "title": "Criteria",
          "type": "array"
        },
        "matching_skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Matching Skills",
          "type": "array"
        },
        "missing_skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Missing Skills",
          "type": "array"
        }
      },
      "required": [
        "global_score"
      ],
      "title": "MatchingOut",
      "type": "object"
    },
    "ProjectOut": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 200,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "description": {
          "default": "",
          "maxLength": 1000,
          "title": "Description",
          "type": "string"
        },
        "technologies": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Technologies",
          "type": "array"
        }
      },
      "required": [
        "name"
      ],
      "title": "ProjectOut",
      "type": "object"
    },
    "StructuredRequirementsOut": {
      "additionalProperties": false,
      "properties": {
        "required_degree": {
          "default": "",
          "maxLength": 300,
          "title": "Required Degree",
          "type": "string"
        },
        "minimum_experience_years": {
          "default": 0,
          "maximum": 80.0,
          "minimum": 0.0,
          "title": "Minimum Experience Years",
          "type": "number"
        },
        "required_skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Required Skills",
          "type": "array"
        },
        "preferred_skills": {
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Preferred Skills",
          "type": "array"
        },
        "required_certifications": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Required Certifications",
          "type": "array"
        },
        "languages": {
          "items": {
            "type": "string"
          },
          "maxItems": 30,
          "title": "Languages",
          "type": "array"
        },
        "other_requirements": {
          "default": "",
          "maxLength": 5000,
          "title": "Other Requirements",
          "type": "string"
        }
      },
      "title": "StructuredRequirementsOut",
      "type": "object"
    }
  },
  "properties": {
    "requirements": {
      "$ref": "#/$defs/StructuredRequirementsOut"
    },
    "profile": {
      "$ref": "#/$defs/ExtractedProfileOut"
    },
    "document_verification": {
      "$ref": "#/$defs/DocumentVerificationOut"
    },
    "matching": {
      "$ref": "#/$defs/MatchingOut"
    }
  },
  "required": [
    "requirements",
    "profile",
    "document_verification",
    "matching"
  ],
  "title": "ReportInput",
  "type": "object"
}
```

### Sortie : `ReportOut`

```json
{
  "$defs": {
    "Criterion": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 100,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "score": {
          "maximum": 100.0,
          "minimum": 0.0,
          "title": "Score",
          "type": "number"
        },
        "weight": {
          "maximum": 100.0,
          "minimum": 0.0,
          "title": "Weight",
          "type": "number"
        },
        "justification": {
          "maxLength": 1000,
          "minLength": 1,
          "title": "Justification",
          "type": "string"
        },
        "evidence": {
          "items": {
            "type": "string"
          },
          "maxItems": 50,
          "title": "Evidence",
          "type": "array"
        }
      },
      "required": [
        "name",
        "score",
        "weight",
        "justification"
      ],
      "title": "Criterion",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "strengths": {
      "items": {
        "type": "string"
      },
      "maxItems": 50,
      "title": "Strengths",
      "type": "array"
    },
    "gaps": {
      "items": {
        "type": "string"
      },
      "maxItems": 50,
      "title": "Gaps",
      "type": "array"
    },
    "inconsistencies": {
      "items": {
        "type": "string"
      },
      "maxItems": 50,
      "title": "Inconsistencies",
      "type": "array"
    },
    "criteria": {
      "items": {
        "$ref": "#/$defs/Criterion"
      },
      "maxItems": 50,
      "title": "Criteria",
      "type": "array"
    },
    "conclusion": {
      "maxLength": 2000,
      "minLength": 1,
      "title": "Conclusion",
      "type": "string"
    },
    "human_decision_reminder": {
      "default": "La décision finale appartient à un humain.",
      "maxLength": 300,
      "minLength": 1,
      "title": "Human Decision Reminder",
      "type": "string"
    }
  },
  "required": [
    "conclusion"
  ],
  "title": "ReportOut",
  "type": "object"
}
```
