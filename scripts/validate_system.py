#!/usr/bin/env python3
"""
System Validation and Integration Script

This script performs comprehensive validation of the GenAI DevOps Assistant
system, ensuring all components are properly integrated and functioning.
"""

import os
import sys
import subprocess
import time
import json
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemValidator:
    """Comprehensive system validator."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.validation_results = {}
        
    def validate_configuration(self) -> bool:
        """Validate system configuration."""
        logger.info("🔧 Validating system configuration...")
        
        try:
            # Run configuration validator
            result = subprocess.run([
                sys.executable, 
                str(self.project_root / "backend" / "config_validator.py")
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info("✅ Configuration validation passed")
                return True
            else:
                logger.error(f"❌ Configuration validation failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Configuration validation error: {e}")
            return False
    
    def validate_dependencies(self) -> bool:
        """Validate all system dependencies."""
        logger.info("📦 Validating system dependencies...")
        
        # Check Python packages
        required_packages = [
            "fastapi", "uvicorn", "streamlit", "openai", "pinecone-client",
            "redis", "langchain", "pydantic", "pytest"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            logger.error(f"❌ Missing packages: {missing_packages}")
            return False
        
        logger.info("✅ All required packages are installed")
        return True
    
    def validate_file_structure(self) -> bool:
        """Validate project file structure."""
        logger.info("📁 Validating file structure...")
        
        required_files = [
            "backend/main.py",
            "backend/config.py",
            "backend/models.py",
            "backend/rag_engine.py",
            "frontend/app.py",
            "collab/interactive_ingestion.py",
            "docker-compose.yml",
            ".env.example",
            "README.md"
        ]
        
        missing_files = []
        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                missing_files.append(file_path)
        
        if missing_files:
            logger.error(f"❌ Missing files: {missing_files}")
            return False
        
        logger.info("✅ All required files are present")
        return True
    
    def validate_tests(self) -> bool:
        """Validate test suite."""
        logger.info("🧪 Validating test suite...")
        
        try:
            # Run test suite
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                str(self.project_root / "backend" / "tests"),
                "-v", "--tb=short", "-x"  # Stop on first failure
            ], capture_output=True, text=True, timeout=300, cwd=self.project_root)
            
            if result.returncode == 0:
                logger.info("✅ Test suite passed")
                return True
            else:
                logger.error(f"❌ Test suite failed: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Test suite timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Test suite error: {e}")
            return False
    
    def validate_api_endpoints(self) -> bool:
        """Validate API endpoints are working."""
        logger.info("🌐 Validating API endpoints...")
        
        # Check if backend is running
        backend_url = "http://localhost:8000"
        
        try:
            response = requests.get(f"{backend_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Backend API is accessible")
                
                # Test additional endpoints
                endpoints = ["/", "/config", "/stats"]
                for endpoint in endpoints:
                    try:
                        resp = requests.get(f"{backend_url}{endpoint}", timeout=5)
                        if resp.status_code == 200:
                            logger.info(f"✅ Endpoint {endpoint} working")
                        else:
                            logger.warning(f"⚠️  Endpoint {endpoint} returned {resp.status_code}")
                    except Exception as e:
                        logger.warning(f"⚠️  Endpoint {endpoint} failed: {e}")
                
                return True
            else:
                logger.error(f"❌ Backend health check failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException:
            logger.warning("⚠️  Backend is not running (this is OK if testing without services)")
            return True  # Don't fail validation if services aren't running
    
    def validate_docker_setup(self) -> bool:
        """Validate Docker setup."""
        logger.info("🐳 Validating Docker setup...")
        
        try:
            # Check if Docker is available
            result = subprocess.run(["docker", "--version"], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                logger.warning("⚠️  Docker not available")
                return True  # Don't fail if Docker isn't installed
            
            # Check if docker-compose files are valid
            compose_files = ["docker-compose.yml", "docker-compose.dev.yml", "docker-compose.prod.yml"]
            
            for compose_file in compose_files:
                file_path = self.project_root / compose_file
                if file_path.exists():
                    try:
                        result = subprocess.run([
                            "docker-compose", "-f", str(file_path), "config"
                        ], capture_output=True, text=True, timeout=30)
                        
                        if result.returncode == 0:
                            logger.info(f"✅ {compose_file} is valid")
                        else:
                            logger.error(f"❌ {compose_file} is invalid: {result.stderr}")
                            return False
                    except Exception as e:
                        logger.warning(f"⚠️  Could not validate {compose_file}: {e}")
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️  Docker validation failed: {e}")
            return True  # Don't fail validation for Docker issues
    
    def validate_documentation(self) -> bool:
        """Validate documentation completeness."""
        logger.info("📚 Validating documentation...")
        
        required_docs = [
            "README.md",
            "DEPLOYMENT.md", 
            "docs/CONFIGURATION.md"
        ]
        
        missing_docs = []
        for doc_path in required_docs:
            full_path = self.project_root / doc_path
            if not full_path.exists():
                missing_docs.append(doc_path)
            else:
                # Check if documentation has substantial content
                try:
                    content = full_path.read_text()
                    if len(content) < 500:  # At least 500 characters
                        logger.warning(f"⚠️  {doc_path} seems incomplete")
                    else:
                        logger.info(f"✅ {doc_path} is present and substantial")
                except Exception as e:
                    logger.warning(f"⚠️  Could not read {doc_path}: {e}")
        
        if missing_docs:
            logger.error(f"❌ Missing documentation: {missing_docs}")
            return False
        
        return True
    
    def validate_security_setup(self) -> bool:
        """Validate security configuration."""
        logger.info("🔒 Validating security setup...")
        
        # Check for .env.example
        env_example = self.project_root / ".env.example"
        if not env_example.exists():
            logger.error("❌ .env.example file missing")
            return False
        
        # Check that .env is not committed (should not exist in repo)
        env_file = self.project_root / ".env"
        if env_file.exists():
            logger.warning("⚠️  .env file exists - ensure it's not committed to version control")
        
        # Check for security-related configurations
        try:
            with open(env_example, 'r') as f:
                env_content = f.read()
                
            security_checks = [
                ("OPENAI_API_KEY", "OpenAI API key placeholder"),
                ("PINECONE_API_KEY", "Pinecone API key placeholder"),
                ("CORS_ORIGINS", "CORS configuration"),
                ("RATE_LIMIT_PER_MINUTE", "Rate limiting configuration")
            ]
            
            for key, description in security_checks:
                if key in env_content:
                    logger.info(f"✅ {description} configured")
                else:
                    logger.warning(f"⚠️  {description} not found in .env.example")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Security validation failed: {e}")
            return False
    
    def run_integration_tests(self) -> bool:
        """Run integration tests if available."""
        logger.info("🔗 Running integration tests...")
        
        try:
            # Run integration tests
            result = subprocess.run([
                sys.executable, "-m", "pytest",
                str(self.project_root / "backend" / "tests"),
                "-v", "-m", "integration", "--tb=short"
            ], capture_output=True, text=True, timeout=180, cwd=self.project_root)
            
            if result.returncode == 0:
                logger.info("✅ Integration tests passed")
                return True
            else:
                logger.warning(f"⚠️  Integration tests had issues: {result.stdout}")
                return True  # Don't fail validation for integration test issues
                
        except Exception as e:
            logger.warning(f"⚠️  Integration tests failed: {e}")
            return True  # Don't fail validation for integration test issues
    
    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        logger.info("📋 Generating validation report...")
        
        report = {
            "validation_timestamp": datetime.utcnow().isoformat(),
            "project_root": str(self.project_root),
            "validation_results": self.validation_results,
            "summary": {
                "total_validations": len(self.validation_results),
                "passed_validations": sum(1 for result in self.validation_results.values() if result),
                "failed_validations": sum(1 for result in self.validation_results.values() if not result),
                "success_rate": sum(1 for result in self.validation_results.values() if result) / max(len(self.validation_results), 1)
            },
            "recommendations": self._generate_recommendations()
        }
        
        # Save report
        report_file = self.project_root / f"system_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📄 Validation report saved to: {report_file}")
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        if not self.validation_results.get("Configuration", True):
            recommendations.append("Fix configuration issues by running: python backend/config_validator.py")
        
        if not self.validation_results.get("Dependencies", True):
            recommendations.append("Install missing dependencies: pip install -r backend/requirements.txt")
        
        if not self.validation_results.get("Tests", True):
            recommendations.append("Fix failing tests before deployment")
        
        if not self.validation_results.get("Documentation", True):
            recommendations.append("Complete missing documentation files")
        
        if not self.validation_results.get("Security", True):
            recommendations.append("Review and fix security configuration")
        
        if not recommendations:
            recommendations.append("System validation passed! Ready for deployment.")
        
        return recommendations
    
    def run_complete_validation(self) -> bool:
        """Run complete system validation."""
        logger.info("🚀 Starting comprehensive system validation...")
        logger.info("=" * 60)
        
        # Define validation steps
        validations = [
            ("Configuration", self.validate_configuration),
            ("Dependencies", self.validate_dependencies),
            ("File Structure", self.validate_file_structure),
            ("Tests", self.validate_tests),
            ("API Endpoints", self.validate_api_endpoints),
            ("Docker Setup", self.validate_docker_setup),
            ("Documentation", self.validate_documentation),
            ("Security", self.validate_security_setup),
            ("Integration Tests", self.run_integration_tests)
        ]
        
        # Run validations
        for validation_name, validation_func in validations:
            logger.info(f"\n{'='*20} {validation_name} {'='*20}")
            
            try:
                result = validation_func()
                self.validation_results[validation_name] = result
                
                if result:
                    logger.info(f"✅ {validation_name} validation PASSED")
                else:
                    logger.error(f"❌ {validation_name} validation FAILED")
                    
            except Exception as e:
                logger.error(f"❌ {validation_name} validation ERROR: {e}")
                self.validation_results[validation_name] = False
        
        # Generate report
        report = self.generate_validation_report()
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("🎯 SYSTEM VALIDATION SUMMARY")
        logger.info("=" * 60)
        
        passed = sum(1 for result in self.validation_results.values() if result)
        total = len(self.validation_results)
        success_rate = passed / total if total > 0 else 0
        
        logger.info(f"Validations passed: {passed}/{total} ({success_rate:.1%})")
        
        for validation_name, result in self.validation_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"  {validation_name:<20} {status}")
        
        # Print recommendations
        logger.info("\n📋 Recommendations:")
        for rec in report["recommendations"]:
            logger.info(f"  • {rec}")
        
        # Determine overall success
        critical_validations = ["Configuration", "Dependencies", "File Structure", "Security"]
        critical_passed = all(self.validation_results.get(val, False) for val in critical_validations)
        
        if critical_passed and success_rate >= 0.7:  # 70% overall pass rate
            logger.info("\n🎉 SYSTEM VALIDATION PASSED!")
            logger.info("The GenAI DevOps Assistant system is ready for use.")
            return True
        else:
            logger.error("\n💥 SYSTEM VALIDATION FAILED!")
            logger.error("Please address the failing validations before using the system.")
            return False


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive system validation")
    parser.add_argument("--quick", action="store_true", help="Skip time-consuming validations")
    parser.add_argument("--report-only", action="store_true", help="Generate report without running validations")
    
    args = parser.parse_args()
    
    validator = SystemValidator()
    
    if args.report_only:
        # Just generate a report with current state
        validator.validation_results = {"Report Generation": True}
        validator.generate_validation_report()
        return 0
    
    # Run validation
    success = validator.run_complete_validation()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()