"""
LaunchDarkly Policy Validator

This module provides functionality to validate LaunchDarkly custom role policies
against the official LaunchDarkly resource actions. It helps identify invalid or
deprecated actions that might be present in policies.

The validator can use either a built-in dictionary of resource actions or load
a custom JSON file with resource actions. It checks each action in each policy
statement against the list of valid actions for the corresponding resource type.

Classes:
    None

Functions:
    load_resource_actions: Loads the LaunchDarkly resource actions from a JSON file
    get_invalid_actions: Identifies invalid actions in custom role policies
    validate_policies: Validates all policies in the provided data

Usage:
    from launchdarkly_policy_similarity import validate_policies
    
    # Validate policies using built-in resource actions
    invalid_actions = validate_policies(data)
    
    # Validate policies using custom resource actions file
    invalid_actions = validate_policies(data, "path/to/resource_actions.json")
"""

import json
import os
import logging
from typing import Dict, List, Any, Optional


# Actions as of 3/12/2025
# https://launchdarkly.com/docs/home/account/role-actions#expand-webhook-actions
launchdarkly_resources_actions = {
    'acct': [
        'createAnnouncement', 'createSamlConfig', 'createScimConfig', 'deleteAccount',
        'deleteAccountToken', 'deleteAnnouncement', 'deleteSamlConfig', 'deleteScimConfig',
        'deleteSubscription', 'getPaymentCard', 'revokeSessions', 'updateAccountOwner',
        'updateAccountToken', 'updateAnnouncement', 'updateBillingContact', 'updateOrganization',
        'updatePaymentCard', 'updateRequireMfa', 'updateSamlDecryptionEnabled', 'updateSamlDefaultRole',
        'updateSamlEnabled', 'updateSamlLogoutUrl', 'updateSamlRequestSigningEnabled',
        'updateSamlRequireSso', 'updateSamlSsoUrl', 'updateSamlX509Certificate',
        'updateSamlX509KeystoreId', 'updateSessionDuration', 'updateSessionRefresh',
        'updateSubscription'
    ],
    'proj/*': [
        'createProject', 'deleteProject', 'updateDefaultClientSideAvailability',
        'updateDefaultReleasePipeline', 'updateIncludeInSnippetByDefault', 'updateProjectFlagDefaults',
        'updateProjectName', 'updateTags', 'viewProject'
    ],
    'proj/*:aiconfig/*': [
        'createAIConfig', 'deleteAIConfig', 'deleteAIConfigVariation', 'updateAIConfig',
        'updateAIConfigVariation'
    ],
    'proj/*:ai-model-config/*': [
        'createAIModelConfig', 'deleteAIModelConfig'
    ],
    'application/*': [
        'createApplication', 'deleteApplication', 'updateApplicationDescription',
        'updateApplicationKind', 'updateApplicationMaintainer', 'createApplicationVersion',
        'deleteApplicationVersion', 'updateApplicationVersionName', 'updateApplicationVersionSupport'
    ],
    'code-reference-repository/*': [
        'createCodeRefsRepository', 'deleteCodeRefsRepository', 'updateCodeRefsRepositoryBranches',
        'updateCodeRefsRepositoryConfiguration', 'updateCodeRefsRepositoryName', 'updateCodeRefsRepositoryOn'
    ],
    'proj/*:context-kind/*': [
        'createContextKind', 'updateContextKind', 'updateAvailabilityForExperiments'
    ],
    'proj/*:env/*:destination/*': [
        'createDestination', 'deleteDestination', 'updateConfiguration', 'updateName', 'updateOn'
    ],
    'domain-verification/*': [
        'createDomainVerification', 'deleteDomainVerification', 'updateDomainVerification'
    ],
    'proj/*:env/*': [
        'createEnvironment', 'deleteEnvironment', 'deleteContextInstance', 'importEventData',
        'updateApiKey', 'updateApprovalSettings', 'updateColor', 'updateConfirmChanges',
        'updateCritical', 'updateDefaultTrackEvents', 'updateMobileKey', 'updateName',
        'updateRequireComments', 'updateSecureMode', 'updateTags', 'updateTtl', 'viewSdkKey'
    ],
    'proj/*:env/*:experiment/*': [
        'createExperiment', 'updateExperiment', 'updateExperimentArchived'
    ],
    'proj/*:layer/*': [
        'createLayer', 'updateLayer', 'updateLayerConfiguration'
    ],
    'proj/*:env/*:flag/*': [
        'stopMeasuredRolloutOnFlagFallthrough', 'stopMeasuredRolloutOnFlagRule', 'updateExpiringTargets',
        'updateFallthrough', 'updateFallthroughWithMeasuredRollout', 'updateFeatureWorkflows',
        'updateMeasuredRolloutConfiguration', 'updateOffVariation', 'updateOn', 'updatePrerequisites',
        'updateRules', 'updateRulesWithMeasuredRollout', 'updateScheduledChanges', 'updateTargets',
        'addReleasePipeline', 'createFlag', 'deleteFlag', 'removeReleasePipeline',
        'replaceReleasePipeline', 'updateClientSideFlagAvailability', 'updateDescription',
        'updateDeprecated', 'updateFlagConfigMigrationSettings', 'updateFlagCustomProperties',
        'updateFlagDefaultVariations', 'updateFlagVariations', 'updateGlobalArchived',
        'updateIncludeInSnippet', 'updateName', 'updateTags', 'updateTemporary', 'createTriggers',
        'deleteTriggers', 'updateFlagSalt', 'updateTrackEvents', 'updateTriggers',
        'applyApprovalRequest', 'bypassRequiredApproval', 'createApprovalRequest', 'createFlagLink',
        'deleteApprovalRequest', 'deleteFlagLink', 'manageFlagFollowers', 'reviewApprovalRequest',
        'updateApprovalRequest', 'updateMaintainer', 'updateFlagLink', 'cloneFlag',
        'copyFlagConfigFrom', 'copyFlagConfigTo', 'updateFlagRuleDescription', 'updateReleasePhaseStatus',
        'toggleFlag'
    ],
    'proj/*:env/*:holdout/*': [
        'addExperimentToHoldout', 'createHoldout', 'removeExperimentFromHoldout',
        'updateHoldoutDescription', 'updateHoldoutMethodology', 'updateHoldoutName',
        'updateHoldoutStatus', 'updateHoldoutRandomizationUnit'
    ],
    'integration/*': [
        'createIntegration', 'deleteIntegration', 'updateConfiguration', 'updateName',
        'updateOn', 'validateConnection'
    ],
    'member/*': [
        'approveDomainMatchedMember', 'createMember', 'deleteMember', 'sendMfaRecoveryCode',
        'sendMfaRequest', 'updateCustomRole', 'updateMemberRoleAttributes', 'updateRole'
    ],
    'proj/*:metric/*': [
        'createMetric', 'deleteMetric', 'updateDescription', 'updateEventDefault',
        'updateEventKey', 'updateMaintainer', 'updateName', 'updateNumeric',
        'updateNumericSuccess', 'updateNumericUnit', 'updateOn', 'updateRandomizationUnits',
        'updateSelector', 'updateTags', 'updateUnitAggregationType', 'updateUrls'
    ],
    'proj/*:metric-group/*': [
        'createMetricGroup', 'deleteMetricGroup', 'updateMetricGroupName',
        'updateMetricGroupDescription', 'updateMetricGroupTags', 'updateMetricGroupMaintainer',
        'updateMetricGroupMetrics'
    ],
    'pending-request/*': [
        'updatePendingRequest'
    ],
    'member/*:token/*': [
        'createAccessToken', 'deleteAccessToken', 'resetAccessToken',
        'updateAccessTokenDescription', 'updateAccessTokenName', 'updateAccessTokenPolicy'
    ],
    'relay-proxy-config/*': [
        'createRelayAutoConfiguration', 'deleteRelayAutoConfiguration', 'resetRelayAutoConfiguration',
        'updateRelayAutoConfigurationName', 'updateRelayAutoConfigurationPolicy'
    ],
    'proj/*:release-pipeline/*': [
        'createReleasePipeline', 'deleteReleasePipeline', 'updateReleasePipelineDescription',
        'updateReleasePipelineName', 'updateReleasePipelinePhase', 'updateReleasePipelinePhaseName',
        'updateReleasePipelineTags'
    ],
    'role/*': [
        'createRole', 'deleteRole', 'updateBasePermissions', 'updateDescription',
        'updateMembers', 'updateName', 'updatePolicy', 'updateTokens'
    ],
    'proj/*:env/*:segment/*': [
        'applyApprovalRequest', 'createApprovalRequest', 'createSegment', 'deleteApprovalRequest',
        'deleteSegment', 'reviewApprovalRequest', 'updateApprovalRequest', 'updateDescription',
        'updateExcluded', 'updateExpiringTargets', 'updateIncluded', 'updateName',
        'updateRules', 'updateScheduledChanges', 'updateTags'
    ],
    'service-token/*': [
        'createAccessToken', 'deleteAccessToken', 'resetAccessToken',
        'updateAccessTokenDescription', 'updateAccessTokenName'
    ],
    'team/*': [
        'createTeam', 'deleteTeam', 'updateTeamCustomRoles', 'updateTeamDescription',
        'updateTeamMembers', 'updateTeamName', 'updateTeamPermissionGrants', 'viewTeam'
    ],
    'template/*': [
        'createTemplate', 'deleteTemplate', 'viewTemplate'
    ],
    'webhook/*': [
        'createWebhook', 'deleteWebhook', 'updateName', 'updateOn', 'updateQuery',
        'updateSecret', 'updateStatements', 'updateTags', 'updateUrl'
    ],
    'proj/*:env/*:request/*': [
        'createPendingRequest', 'approvePendingRequest', 'denyPendingRequest', 'viewPendingRequest'
    ],
    'domain/*': [
        'createDomainVerification', 'deleteDomainVerification', 'updateDomainVerification'
    ]
}

def load_resource_actions(file_path: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Load LaunchDarkly resource actions from a JSON file or use the built-in dictionary.
    
    This function attempts to load resource actions from the specified JSON file.
    If the file doesn't exist or there's an error loading it, it falls back to
    the built-in dictionary of resource actions.
    
    Args:
        file_path: Path to the JSON file containing resource actions (optional)
        
    Returns:
        Dictionary mapping resource types to lists of valid actions
        
    Example:
        resource_actions = load_resource_actions("./resource_actions.json")
    """
    logger = logging.getLogger(__name__)
    if not file_path:
        logger.info("No file path provided, using built-in resource actions dictionary")
        return launchdarkly_resources_actions

    logger.info(f"Loading resource actions from path [{file_path}]")

    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                # Remove the "export const" part if it exists
                if content.startswith('export const'):
                    content = content[content.find('{'):]
                return json.loads(content)
        except Exception as e:
            logger.warning(f"Error loading resource actions from {file_path}: {e}")
            logger.warning("Using built-in resource actions dictionary instead")
    
    return launchdarkly_resources_actions

def get_invalid_actions(roles: List[Dict[str, Any]], resource_actions: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Identify invalid actions in custom role policies.
    
    This function checks each action in each policy statement against the list of
    valid actions for the corresponding resource type. Actions that are not found
    in the valid actions list are considered invalid.
    
    Args:
        roles: List of custom role objects from LaunchDarkly
        resource_actions: Dictionary mapping resource types to lists of valid actions
        
    Returns:
        Dictionary mapping role keys to lists of invalid actions
        
    Example:
        invalid_actions = get_invalid_actions(roles, resource_actions)
    """
    invalid_policies = {}
    
    for role in roles:
        policy = role.get('policy', [])
        
        for statement in policy:
            # Get actions from either actions or notActions
            actions = statement.get('actions', []) or statement.get('notActions', [])
            
            for action in actions:
                # Skip wildcard actions
                if action == "*":
                    continue
                
                # Check if the action is valid for any resource type
                action_found = False
                for resource_type, valid_actions in resource_actions.items():
                    if action in valid_actions:
                        action_found = True
                        break
                
                if not action_found:
                    # Add the invalid action to the result
                    if role['key'] not in invalid_policies:
                        invalid_policies[role['key']] = []
                    
                    if action not in invalid_policies[role['key']]:
                        invalid_policies[role['key']].append(action)
    
    return invalid_policies

def validate_policies(data: Dict[str, Any], resource_actions_file: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Validate all policies in the provided data.
    
    This function loads resource actions from the specified file or uses the built-in
    dictionary, then checks each action in each policy statement against the list of
    valid actions for the corresponding resource type.
    
    Args:
        data: Dictionary containing LaunchDarkly data with roles
        resource_actions_file: Path to the JSON file containing resource actions (optional)
        
    Returns:
        Dictionary mapping role keys to lists of invalid actions
        
    Example:
        invalid_actions = validate_policies(data, "./resource_actions.json")
    """
    resource_actions = load_resource_actions(resource_actions_file)
    return get_invalid_actions(data.get('roles', []), resource_actions) 