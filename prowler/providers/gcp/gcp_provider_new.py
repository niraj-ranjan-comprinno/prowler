import os
import sys
from typing import Any, Optional

from colorama import Fore, Style
from google import auth
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from prowler.lib.logger import logger
from prowler.providers.common.provider import CloudProvider


class GcpProvider(CloudProvider):
    session: Credentials
    default_project_id: str
    project_ids: list
    audit_resources: Optional[Any]
    audit_metadata: Optional[Any]
    audit_config: Optional[dict]

    def __init__(self, arguments):
        logger.info("Instantiating GCP Provider ...")
        input_project_ids = arguments.project_ids
        credentials_file = arguments.credentials_file

        self.session, self.default_project_id = self.setup_session(credentials_file)
        if not self.default_project_id:
            logger.critical("No Project ID associated to Google Credentials.")
            sys.exit(1)

        self.project_ids = []
        accessible_projects = self.get_project_ids()
        if not accessible_projects:
            logger.critical("No Project IDs can be accessed via Google Credentials.")
            sys.exit(1)

        if input_project_ids:
            for input_project in input_project_ids:
                if input_project in accessible_projects:
                    self.project_ids.append(input_project)
                else:
                    logger.critical(
                        f"Project {input_project} cannot be accessed via Google Credentials."
                    )
                    sys.exit(1)
        else:
            # If not projects were input, all accessible projects are scanned by default
            self.project_ids = accessible_projects

        if not arguments.only_logs:
            self.print_credentials()

    def setup_session(self, credentials_file):
        try:
            if credentials_file:
                self.__set_gcp_creds_env_var__(credentials_file)

            return auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        except Exception as error:
            logger.critical(
                f"{error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )
            sys.exit(1)

    def __set_gcp_creds_env_var__(self, credentials_file):
        logger.info(
            "GCP provider: Setting GOOGLE_APPLICATION_CREDENTIALS environment variable..."
        )
        client_secrets_path = os.path.abspath(credentials_file)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = client_secrets_path

    def print_credentials(self):
        # Beautify audited profile, set "default" if there is no profile set
        try:
            getattr(self.session, "_service_account_email")
            profile = (
                self.session._service_account_email
                if self.session._service_account_email is not None
                else "default"
            )
        except AttributeError:
            profile = "default"

        report = f"""
This report is being generated using credentials below:

GCP Account: {Fore.YELLOW}[{profile}]{Style.RESET_ALL}  GCP Project IDs: {Fore.YELLOW}[{", ".join(self.project_ids)}]{Style.RESET_ALL}
"""
        print(report)

    def get_project_ids(self):
        try:
            project_ids = []

            service = discovery.build(
                "cloudresourcemanager", "v1", credentials=self.session
            )

            request = service.projects().list()

            while request is not None:
                response = request.execute()

                for project in response.get("projects", []):
                    project_ids.append(project["projectId"])

                request = service.projects().list_next(
                    previous_request=request, previous_response=response
                )

            return project_ids
        except Exception as error:
            logger.error(
                f"{error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )
            return []