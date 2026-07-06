#!/usr/bin/env python3
"""
Azure Functions Flex Consumption — deployed package import diagnostic.

Run from inside the extracted deployment package directory with PYTHONPATH
already set to include .python_packages/lib/site-packages. Called by the
diagnose-function-app.yml workflow Phase D step.

Exit codes:
  0 — import succeeded (check stdout for function count)
  1 — import failed (check stdout for traceback and diagnosis)
  2 — azure.functions SDK itself could not be imported (foundational failure)
"""

import sys
import os
import json
import traceback

RESULT = {
    "python_version": sys.version,
    "sys_path": sys.path[:5],
    "azure_functions_importable": False,
    "azure_functions_version": None,
    "register_functions_exists_on_FunctionApp": False,
    "register_blueprint_exists_on_FunctionApp": False,
    "function_app_importable": False,
    "function_app_has_app_object": False,
    "registered_function_count": 0,
    "registered_function_names": [],
    "error_type": None,
    "error_message": None,
    "error_traceback": None,
    "failed_at_step": None,
    "diagnosis": None,
    "fix": None,
}

DIVIDER = "=" * 72


def banner(title: str) -> None:
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def print_result_json() -> None:
    print(f"\n\n{DIVIDER}")
    print("  STRUCTURED RESULTS (parsed by workflow)")
    print(DIVIDER)
    print(json.dumps(RESULT, indent=2))


# ── Environment check ─────────────────────────────────────────────────────────

banner("Environment")
print(f"Python:       {sys.version}")
print(f"Working dir:  {os.getcwd()}")
print(f"sys.path[:5]: {sys.path[:5]}")
print(f"PYTHONPATH:   {os.environ.get('PYTHONPATH', '<not set>')}")
print()

cwd_contents = os.listdir(".")
print(f"Working dir contents ({len(cwd_contents)} items):")
for item in sorted(cwd_contents)[:30]:
    kind = "📁" if os.path.isdir(item) else "📄"
    print(f"  {kind} {item}")
if len(cwd_contents) > 30:
    print(f"  ... and {len(cwd_contents) - 30} more")

site_pkgs = ".python_packages/lib/site-packages"
if os.path.isdir(site_pkgs):
    pkgs = os.listdir(site_pkgs)
    print(f"\n.python_packages/lib/site-packages ({len(pkgs)} entries):")
    for p in sorted(pkgs)[:20]:
        print(f"  {p}")
    if len(pkgs) > 20:
        print(f"  ... and {len(pkgs) - 20} more")
else:
    print(f"\n⚠️  {site_pkgs} NOT FOUND — dependencies are not bundled in this package.")
    print("   Fix: Ensure the deploy workflow runs:")
    print("     pip install --upgrade --target=.python_packages/lib/site-packages -r requirements.txt")
    print("   and that .python_packages/ is NOT excluded in .funcignore")

# ── Step 1: azure.functions ───────────────────────────────────────────────────

banner("Step 1: Import azure.functions")
try:
    import azure.functions as func  # noqa: E402

    RESULT["azure_functions_importable"] = True
    RESULT["azure_functions_version"] = getattr(func, "__version__", "unknown")
    print(f"✅ azure.functions {RESULT['azure_functions_version']}")

    has_reg_fn = hasattr(func.FunctionApp, "register_functions")
    has_reg_bp = hasattr(func.FunctionApp, "register_blueprint")
    RESULT["register_functions_exists_on_FunctionApp"] = has_reg_fn
    RESULT["register_blueprint_exists_on_FunctionApp"] = has_reg_bp

    print(f"   FunctionApp.register_functions  : {'✅ EXISTS' if has_reg_fn else '❌ MISSING'}")
    print(f"   FunctionApp.register_blueprint  : {'exists (alias)' if has_reg_bp else '❌ DOES NOT EXIST — calling this raises AttributeError'}")

    if not has_reg_fn:
        RESULT["diagnosis"] = "azure-functions SDK does not have FunctionApp.register_functions — SDK version may be too old or wrong package installed."
        RESULT["fix"] = "Upgrade azure-functions in requirements.txt (>= 1.17.0 is needed for register_functions)."
        print(f"\n⚠️  Diagnosis: {RESULT['diagnosis']}")
        print(f"   Fix:       {RESULT['fix']}")

except Exception as exc:
    RESULT["failed_at_step"] = "azure.functions"
    RESULT["error_type"] = type(exc).__name__
    RESULT["error_message"] = str(exc)
    RESULT["error_traceback"] = traceback.format_exc()
    RESULT["diagnosis"] = f"azure.functions package itself failed to import: {exc}"
    RESULT["fix"] = (
        "Ensure azure-functions is listed in requirements.txt and that the "
        "pip install --target=.python_packages/lib/site-packages step ran successfully. "
        "Check the deploy workflow log for pip errors."
    )
    print(f"❌ azure.functions import FAILED: {exc}")
    print("\nFULL TRACEBACK:")
    print(RESULT["error_traceback"])
    print_result_json()
    sys.exit(2)

# ── Step 2: function_app.py ───────────────────────────────────────────────────

banner("Step 2: Import function_app")

if not os.path.isfile("function_app.py"):
    RESULT["failed_at_step"] = "function_app.py file not found"
    RESULT["error_type"] = "FileNotFoundError"
    RESULT["error_message"] = "function_app.py does not exist in the deployed package"
    RESULT["diagnosis"] = "function_app.py is missing from the deployed zip entirely."
    RESULT["fix"] = (
        "Verify function_app.py is at the repo root (not inside a subdirectory). "
        "Check .funcignore — if it excludes *.py or has an overly broad pattern, "
        "function_app.py will be omitted. Also confirm the deploy workflow packages "
        "with `package: .` pointing to the repo root."
    )
    print(f"❌ {RESULT['error_message']}")
    print_result_json()
    sys.exit(1)

print("function_app.py found — attempting import...")
print()

try:
    import function_app  # noqa: E402

    RESULT["function_app_importable"] = True
    print("✅ function_app imported successfully")

    if not hasattr(function_app, "app"):
        print("⚠️  function_app module has no top-level 'app' object")
        print(f"   Available names: {[n for n in dir(function_app) if not n.startswith('_')]}")
        RESULT["diagnosis"] = "function_app.py was imported but has no 'app' FunctionApp object."
        RESULT["fix"] = "Ensure function_app.py contains: app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)"
    else:
        RESULT["function_app_has_app_object"] = True
        app = function_app.app
        print(f"   app type: {type(app).__qualname__}")

        # Enumerate registered functions via multiple introspection paths
        fn_count = 0
        fn_names = []
        for attr in (
            "_function_builders",
            "_functions",
            "_function_builders_dict",
            "_function_builders_by_name",
            "_functions_dict",
        ):
            val = getattr(app, attr, None)
            if isinstance(val, dict) and val:
                fn_count = len(val)
                fn_names = list(val.keys())[:30]
                print(f"   Registered functions (via app.{attr}): {fn_count}")
                for name in fn_names:
                    print(f"     - {name}")
                break
        else:
            # Fallback: introspect for any function-shaped attrs
            candidates = [
                a for a in dir(app)
                if any(k in a.lower() for k in ("func", "blueprint", "builder", "trigger", "route"))
            ]
            print(f"   Could not find function registry via standard attrs.")
            print(f"   Function-related app attributes: {candidates}")

        RESULT["registered_function_count"] = fn_count
        RESULT["registered_function_names"] = fn_names

        if fn_count == 0:
            RESULT["diagnosis"] = (
                "function_app.py imported without error but 0 functions are registered "
                "in the FunctionApp object. Blueprints may not be passed to register_functions()."
            )
            RESULT["fix"] = (
                "Ensure every Blueprint is registered:\n"
                "  app.register_functions(auth_blueprint)\n"
                "  app.register_functions(boardroom_blueprint)\n"
                "  # etc.\n"
                "Also verify each Blueprint uses @blueprint.route(), @blueprint.timer_trigger(), etc."
            )
            print(f"\n⚠️  Diagnosis: {RESULT['diagnosis']}")
        else:
            print(f"\n✅ {fn_count} function(s) registered — import and registration are healthy.")

except AttributeError as exc:
    tb = traceback.format_exc()
    RESULT["failed_at_step"] = "function_app (AttributeError)"
    RESULT["error_type"] = "AttributeError"
    RESULT["error_message"] = str(exc)
    RESULT["error_traceback"] = tb

    print(f"❌ AttributeError: {exc}")
    print("\nFULL TRACEBACK:")
    print(tb)

    if "register_blueprint" in str(exc) or "register_blueprint" in tb:
        RESULT["diagnosis"] = (
            "app.register_blueprint() is called in function_app.py but this method does NOT "
            "exist on func.FunctionApp. It raises AttributeError at import time, which prevents "
            "the Functions host from indexing any functions."
        )
        RESULT["fix"] = (
            "In function_app.py, replace every:\n"
            "  app.register_blueprint(<blueprint>)\n"
            "with:\n"
            "  app.register_functions(<blueprint>)\n"
            "register_functions() is the correct method in the azure-functions Python v2 SDK."
        )
    else:
        RESULT["diagnosis"] = f"AttributeError during import: {exc}"
        RESULT["fix"] = "Inspect the traceback above to find which attribute is missing and fix the calling code."

    print(f"\n🎯 Diagnosis: {RESULT['diagnosis']}")
    print(f"   Fix:      {RESULT['fix']}")
    print_result_json()
    sys.exit(1)

except ImportError as exc:
    tb = traceback.format_exc()
    RESULT["failed_at_step"] = "function_app (ImportError)"
    RESULT["error_type"] = "ImportError"
    RESULT["error_message"] = str(exc)
    RESULT["error_traceback"] = tb

    print(f"❌ ImportError: {exc}")
    print("\nFULL TRACEBACK:")
    print(tb)

    # Extract the missing module name
    missing = str(exc).replace("No module named ", "").strip("'")
    RESULT["diagnosis"] = f"Module '{missing}' could not be found during import of function_app."
    RESULT["fix"] = (
        f"Ensure '{missing}' is either:\n"
        f"  a) Listed in requirements.txt (for third-party packages), or\n"
        f"  b) Present as a directory at the repo root (for your own packages like business_infinity).\n"
        f"Then redeploy. Check that .funcignore does not exclude '{missing.split('.')[0]}/'."
    )

    print(f"\n🎯 Diagnosis: {RESULT['diagnosis']}")
    print(f"   Fix:      {RESULT['fix']}")
    print_result_json()
    sys.exit(1)

except SyntaxError as exc:
    tb = traceback.format_exc()
    RESULT["failed_at_step"] = f"function_app (SyntaxError at {exc.filename}:{exc.lineno})"
    RESULT["error_type"] = "SyntaxError"
    RESULT["error_message"] = f"{exc.msg} (line {exc.lineno}: {exc.text})"
    RESULT["error_traceback"] = tb
    RESULT["diagnosis"] = f"Python syntax error in {exc.filename} at line {exc.lineno}: {exc.msg}"
    RESULT["fix"] = f"Fix the syntax error: {exc.text}"

    print(f"❌ SyntaxError: {RESULT['error_message']}")
    print("\nFULL TRACEBACK:")
    print(tb)
    print_result_json()
    sys.exit(1)

except Exception as exc:
    tb = traceback.format_exc()
    RESULT["failed_at_step"] = f"function_app ({type(exc).__name__})"
    RESULT["error_type"] = type(exc).__name__
    RESULT["error_message"] = str(exc)
    RESULT["error_traceback"] = tb
    RESULT["diagnosis"] = f"{type(exc).__name__} during function_app import: {exc}"
    RESULT["fix"] = "Inspect the full traceback above."

    print(f"❌ {type(exc).__name__}: {exc}")
    print("\nFULL TRACEBACK:")
    print(tb)
    print(f"\n🎯 Diagnosis: {RESULT['diagnosis']}")
    print_result_json()
    sys.exit(1)

# ── All good ──────────────────────────────────────────────────────────────────

print_result_json()
sys.exit(0)
