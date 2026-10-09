"""Versioned compatibility gate shared by scene compiler and package loader."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def target(identity='de2-115-fixed-v1'):
    names={'de2-115-fixed-v1':'de2-115-capabilities.json','de2-115-fixed-v2':'de2-115-interactive-capabilities.json'}
    if identity not in names: raise ValueError('Unsupported hardware target/runtime ABI')
    return json.loads((ROOT/'profiles'/names[identity]).read_text())

def validate(requirements):
    if not isinstance(requirements, dict) or set(requirements) != {'id', 'runtime_abi', 'required_features'}:
        raise ValueError('Target declaration requires id, runtime_abi and required_features')
    caps = target(requirements['id'])
    if requirements['id'] != caps['id'] or type(requirements['runtime_abi']) is not int or requirements['runtime_abi'] != caps['runtime_abi']:
        raise ValueError('Unsupported hardware target/runtime ABI')
    features = requirements['required_features']
    if not isinstance(features, list) or not all(isinstance(f, str) for f in features):
        raise ValueError('Required features must be a string list')
    if len(set(features))!=len(features):raise ValueError('Required features must be unique')
    unsupported = sorted(set(features) - set(caps['features']))
    if unsupported:
        raise ValueError('Target cannot provide required features: '+', '.join(unsupported))
    return caps
