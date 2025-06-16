import json
import os
from typing import Dict, List
import math
from tqdm import tqdm
import logging

class SimilarityReport:
    """
    Generates HTML reports comparing LaunchDarkly custom role policies.
    
    This class is responsible for creating an interactive HTML report that visualizes
    policy similarities, role assignments, and team access patterns. It processes
    the data from the LaunchDarkly API and policy similarity analysis to generate
    a comprehensive report with interactive features.
    
    Attributes:
        output_file (str): Path to save the HTML report
        ldc_cache_data (Dict): Dictionary containing cached data from LaunchDarkly
        policy_data (Dict): Dictionary containing policy similarity data
        logger: Logger instance for this class
    """

    def __init__(self, output_file: str, ldc_cache_data: Dict, policy_data: Dict, min_similarity: float, invalid_actions: Dict = None):
        """
        Initialize the SimilarityReport generator.
        
        Args:
            output_file (str): Path to save the HTML report
            ldc_cache_data (Dict): Dictionary containing cached data from LaunchDarkly
            policy_data (Dict): Dictionary containing policy similarity data
            min_similarity (float): Minimum similarity score to include in the report
        """
        self.output_file = output_file  
        self.ldc_cache_data = ldc_cache_data
        self.policy_data = policy_data
        self.min_similarity = min_similarity
        self.invalid_actions = invalid_actions
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"SimilarityReport() output_file: {self.output_file}")
        self.logger.debug(f"SimilarityReport() invalid_actions: {invalid_actions}")
        self.logger.debug(f"SimilarityReport() policy_data: {policy_data}")
            
    def generate_report(self) -> None:
        """
        Generate the HTML report and save it to the output file.
        
        This method generates the complete HTML report, including:
        - Summary statistics
        - Invalid actions section (if available)
        - Teams project access table
        - Similarity graph
        - Role cards with policy details
        
        The report is saved to the output file specified during initialization.
        Static files (CSS and JavaScript) are copied to the same directory.
        
        If an invalid_actions.json file exists in the same directory as the output file,
        it will be loaded and included in the report.
        
        Returns:
            None
        """
        # Generate and save HTML
        html_content = self._generate_html_report()
        with open(self.output_file, 'w') as f:
            f.write(html_content)

        self._copy_static_files()

    def _copy_static_files(self) -> None:
        """
        Copy static CSS and JS files to the output directory.
        
        This method ensures that the necessary styling and interactive functionality
        are available for the HTML report by copying the required files to the
        output directory.
        """
        # Get output directory path
        output_dir = os.path.dirname(self.output_file)

        # Define static file mappings
        static_files = {
            'reports_styles.css': os.path.join(os.path.dirname(__file__), 'reports_styles.css'),
            'reports.js': os.path.join(os.path.dirname(__file__), 'reports.js')
        }

        # Copy each static file
        for dest_name, src_path in static_files.items():
            dest_path = os.path.join(output_dir, dest_name)
            
            try:
                with open(src_path, 'r') as src_file, open(dest_path, 'w') as dest_file:
                    dest_file.write(src_file.read())
            except Exception as e:
                self.logger.error(f"Error copying {src_path} to {dest_path}: {e}")

    def _get_color_class(self, similarity_score: float) -> str:
        """Convert similarity score to CSS color class."""
        if similarity_score >= 0.9:
            return "similarity high"
        elif similarity_score >= 0.7:
            return "similarity medium"
        else:
            return "similarity low"

    def _format_percentage(self, similarity_score: float) -> str:
        """Convert similarity score to percentage string."""
        return f"{math.floor(similarity_score * 100)}%"
    
    def _generate_similar_roles_policy_html(self, parent_key: str, similar_roles: List[Dict], role_info: Dict) -> str:
        """
        Generate HTML for similar roles' policy sections with side-by-side comparison.
        
        Args:
            parent_key (str): Key of the parent role being compared
            similar_roles (List[Dict]): List of similar roles with their policies
            role_info (Dict): Information about the parent role
            
        Returns:
            str: HTML string containing side-by-side policy comparisons
        """
        roles_html = []
        for role in similar_roles:
            role_id = role.get('id', '')
            role_name = role.get('policy_name', '')
            policy = role.get('policy', {})
            policy_json = json.loads(policy)
            roles_html.append(f'''
                <div style="display:none">
                    <div class="policy-column" id="{parent_key}-{role_id}-this-policy">
                        <h4> {role_info['name']}(this policy)</h4>
                        <pre>{json.dumps(role_info['policy'], indent=2)}</pre>
                    </div>

                    <div class="policy-column" id="{parent_key}-{role_id}-that-policy">
                        <h4>{role_name}</h4>
                        <pre>{json.dumps(policy_json, indent=2)}</pre>
                    </div>
                </div>
                <div id="{parent_key}-{role_id}" class="similar-policy">
                    <div class="similar-policy-header">
                        <div class="role-title">Diff between "{role_info['name']}" (<span style="color: #f3a4a4;font-weight:bold;">RED</span>) and "{role_name}" (<span style="color: #4ee67d;font-weight:bold;">GREEN</span>)</div>
                        <button class="close-button" onclick="togglePolicy('{parent_key}-{role_id}')">×</button>
                    </div>

                    <div class="policy-comparison">
                      
                        <div class="policy-column" id="{parent_key}-{role_id}-diff-container-group">
                            <h4>{role_name} : {role_id}</h4>
                            <div id="{parent_key}-{role_id}-diff-container"></div>
                            <button class="toggle-annotated-button" onclick="toggleAnnotatedDiff('{parent_key}-{role_id}-diff-annotated-container')">
                                Show Annotated Diff
                            </button>
                            <div id="{parent_key}-{role_id}-diff-annotated-container" class="annotated-diff hidden">
                                <div class="detail-header">
                                    <h4>Annotated Diff</h4>
                                    <button class="close-button" onclick="toggleAnnotatedDiff('{parent_key}-{role_id}-diff-annotated-container')">×</button>
                                </div>
                            </div>
                        </div>
                        <div class="policy-column" id="{parent_key}-{role_id}-this-policy">
                            <h4> {role_info['name']}(this policy)</h4>
                            <pre>{json.dumps(role_info['policy'], indent=2)}</pre>
                        </div>
                    </div>
                    <div class="close-button-container">
                        <button class="close-button-end-of-container" onclick="togglePolicy('{parent_key}-{role_id}')" >End of Container (click to close)</button>
                    </div>
                </div>
            ''')
        return '\n'.join(roles_html)
    
    def _generate_similar_roles_html(self, parent_key: str, similar_roles: List[Dict]) -> str:
        """
        Generate HTML for similar roles section with clickable pills.
        Shows "No similar roles found" if list is empty.
        
        Args:
            parent_key (str): Key of the parent role
            similar_roles (List[Dict]): List of similar roles with similarity scores
            
        Returns:
            str: HTML string containing clickable role pills with similarity scores
        """
        default_html = r'''
                  <div class="similar-role-pill" onclick="togglePolicy('{parent_key}-{role_id}')">
                        No similar roles found
                 </div>
        '''
        if not similar_roles:
            return default_html
        
        roles_html = []
        for role in similar_roles:
            score = role.get("similarity_score", 0)
            color_class = self._get_color_class(score)
            role_id = role.get('id', '')
            role_name = role.get('policy_name', '')
            
            roles_html.append(f'''
                <div class="similar-role-pill" onclick="togglePolicy('{parent_key}-{role_id}')">
                        {role_name}
                        <span class="{color_class}">{self._format_percentage(score)}</span>
                 </div>
      
            ''')
        
        return '\n'.join(roles_html)
    
    def _getRoleInfo(self, role_key: str) -> Dict:
        role_info = next((role for role in self.ldc_cache_data['roles'] if role['key'] == role_key), None)
        return role_info

    def _get_percent_value_class(self, value: int, inverse: bool = False) -> str:
        css_class ="value-good" 
        if inverse:
            
            if value > 20:
                css_class = "value-zero"
            elif value <= 10 and value > 5:
                css_class = "value-low"
        else:
            if value == 0:
                css_class= "value-zero"
            elif value <= 75:
                css_class= "value-low"

        return css_class
    
    def _get_value_class_bad_good(self, value: int) -> str:
        
        return "value-good" if value == 0 else "value-bad"
        
    
    def _get_value_class(self, value: int) -> str:
        css_class ="value-good" 

        if value == 0:
            css_class= "value-zero"
        elif value <= 2:
            css_class= "value-low"
  
        return css_class
    
    def _get_indicator_class(self, value: int) -> str:
        css_class ="status-good" 

        if value == 0:
            css_class= "status-critical"
        elif value <= 2:
            css_class= "status-warning"
  
        return css_class
    def _generate_policy_detail_html(self, role_info: Dict, role_key: str) -> str:
        self.logger.debug(f"_generate_policy_detail_html() start.")
        # Format the teams and members data for display
        teams_assigned = ",".join([f"{m}" for m in role_info['teams']])
        members_assigned = ",".join([f"{m}" for m in role_info['members']])
        
        # Format teams list for display
        teams_list = ""
        if teams_assigned:
            teams = teams_assigned.split(',')
            teams_list = "\n".join([f"<li>{team}</li>" for team in teams if team])
        
        # Format members list for display
        members_list = ""
        if members_assigned:
            members = members_assigned.split(',')
            members_list = "\n".join([f"<li>{member}</li>" for member in members if member])
        
        teamClassValue = self._get_value_class(role_info.get('total_teams', 0) if role_info else 0)
        teamToggleValue=role_info['total_teams'] if role_info else 'Not defined'
        memberClassValue = self._get_value_class(role_info.get('total_members', 0) if role_info else 0)
        memberToggleValue=role_info['total_members'] if role_info else 'Not defined'
        invliadActionsLen = len(self.invalid_actions.get(role_key, [])) if self.invalid_actions is not None else 0
        invalidActionsClassValue = self._get_value_class_bad_good(invliadActionsLen)
        invalidActionsToggleValue=invliadActionsLen if role_info else 'Not defined'
        return f'''
            <div class="role-meta">Key: {role_key}</div>
            <div class="role-meta">ID:{role_info['_id'] if role_info else 'Not defined'}</div>
            <div class="role-description">Description:{role_info['description'] if role_info else 'Not defined'}</div>

          
            <div class="statistics-card">
                <div class="stats-header">
                    <h4 class="stats-header-title">Assigned to</h4>
                </div>
                <div class="stats-body">
                    <div class="stat-item">
                        
                        <div class="stat-label">Teams</div>
                        <div class="stat-value {teamClassValue}" onclick="toggleDetailPanel('teams-{role_key}')">{teamToggleValue}</div>
                        <div id="teams-{role_key}" class="detail-panel teams-panel hidden">
                            <div class="detail-header">
                                <h4>Teams Assigned</h4>
                                <button class="close-button" onclick="toggleDetailPanel('teams-{role_key}')">×</button>
                            </div>
                            <ul class="detail-list">
                                {teams_list or "<li>No teams assigned</li>"}
                            </ul>
                        </div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Members</div>
                        <div class="stat-value {memberClassValue}" onclick="toggleDetailPanel('members-{role_key}')">{memberToggleValue}</div>
                        <div id="members-{role_key}" class="detail-panel members-panel hidden">
                            <div class="detail-header">
                                <h4>Members Assigned</h4>
                                <button class="close-button" onclick="toggleDetailPanel('members-{role_key}')">×</button>
                            </div>
                            <ul class="detail-list">
                                {members_list or "<li>No members assigned</li>"}
                            </ul>
                        </div>
                    </div>

                    <div class="stat-item">
                        <div class="stat-label">Invalid Actions</div>
                        <div class="stat-value {invalidActionsClassValue}" onclick="toggleDetailPanel('invalid-actions-{role_key}')">{invalidActionsToggleValue}</div>
                        <div id="invalid-actions-{role_key}" class="detail-panel invalid-actions-panel hidden">
                            <div class="detail-header">
                                <h4>Invalid Actions</h4>
                                <button class="close-button" onclick="toggleDetailPanel('invalid-actions-{role_key}')">×</button>
                            </div>
                            <ul class="detail-list">
                                {self._create_invalid_action_pill(self.invalid_actions[role_key]) if invliadActionsLen > 0 else "No Invalid actions"}
                            </ul>
                        </div>
                    </div>

                </div>
            </div>
            
            <div class="metadata-section">
              <div class="expand-toggle">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M16.59 8.59L12 13.17L7.41 8.59L6 10L12 16L18 10L16.59 8.59Z" fill="#0075FF"></path>
                </svg>
                Show Policy
            </div>
            <div class="policy-preview">
                <pre>{json.dumps(role_info['policy'], indent=2) if role_info else 'Undefined'}</pre>
                <div class="policy-preview-fade"></div>
            </div>
            </div>
            
            
        '''

    def _generate_similarity_graph_data(self) -> Dict:
        """
        Generate data for the similarity graph visualization.
        
        This method identifies roles with similarity scores above the threshold
        and creates a data structure for visualizing their relationships.
        
        Args:
            threshold (float): Minimum similarity score to include (default: 0.95)
            
        Returns:
            Dict: Graph data structure with nodes and links
        """
        nodes = []
        links = []
        node_ids = set()
        threshold = self.min_similarity

        # First pass: collect all roles that have similar roles above threshold
        for role_key, similar_roles in self.policy_data.items():
            role_info = self._getRoleInfo(role_key)
            if not role_info:
                continue
                
            # Check if this role has any similar roles above threshold
            has_high_similarity = any(
                role.get('similarity_score', 0) >= threshold 
                for role in similar_roles
            )
            
            if has_high_similarity or any(role_key == similar['id'] for similar_list in self.policy_data.values() for similar in similar_list if similar.get('similarity_score', 0) >= threshold):
                if role_key not in node_ids:
                    node_ids.add(role_key)
                    nodes.append({
                        'id': role_key,
                        'name': role_info.get('name', role_key),
                        'type': self._determine_role_type(role_key)
                    })
        
        # Second pass: create links between highly similar roles
        for role_key, similar_roles in self.policy_data.items():
            if role_key not in node_ids:
                continue
                
            for similar in similar_roles:
                similar_id = similar.get('id')
                similarity_score = similar.get('similarity_score', 0)
                
                if similar_id in node_ids and similarity_score >= threshold:
                    links.append({
                        'source': role_key,
                        'target': similar_id,
                        'value': similarity_score
                    })
        
        return {
            'nodes': nodes,
            'links': links
        }
        
    def _find_similarity_clusters(self) -> List[Dict]:
        """
        Find closed loops (similarity clusters) in the graph.
        
        A similarity cluster is a group of roles where each role is similar to at least one other role
        in the group, and there is a path from any role to any other role in the group.
        
        Args:
            threshold (float): Minimum similarity score to include
            
        Returns:
            List[Dict]: List of clusters, each containing nodes and average similarity score
        """
        threshold = self.min_similarity
        graph_data = self._generate_similarity_graph_data()
        nodes = graph_data['nodes']
        links = graph_data['links']
        
        # Create an adjacency list representation of the graph
        adjacency_list = {}
        for node in nodes:
            adjacency_list[node['id']] = []
            
        for link in links:
            source = link['source']
            target = link['target']
            value = link['value']
            adjacency_list[source].append({'id': target, 'value': value})
        
        # Find all strongly connected components (clusters)
        visited = set()
        clusters = []
        
        def find_cycles(node_id, path=None, visited_in_path=None):
            if path is None:
                path = []
            if visited_in_path is None:
                visited_in_path = set()
                
            path.append(node_id)
            visited_in_path.add(node_id)
            
            cycles = []
            
            for neighbor in adjacency_list[node_id]:
                neighbor_id = neighbor['id']
                
                if neighbor_id in visited_in_path:
                    # Found a cycle
                    cycle_start_index = path.index(neighbor_id)
                    cycle = path[cycle_start_index:]
                    if len(cycle) > 2:  # Only consider cycles with at least 3 nodes
                        cycles.append(cycle)
                elif neighbor_id not in visited:
                    sub_cycles = find_cycles(neighbor_id, path.copy(), visited_in_path.copy())
                    cycles.extend(sub_cycles)
            
            return cycles
        
        # Find all cycles in the graph
        all_cycles = []
        for node_id in adjacency_list:
            if node_id not in visited:
                visited.add(node_id)
                cycles = find_cycles(node_id)
                all_cycles.extend(cycles)
        
        # Convert cycles to clusters
        for cycle in all_cycles:
            # Get node details
            cluster_nodes = []
            total_similarity = 0
            link_count = 0
            
            for node_id in cycle:
                node_info = next((node for node in nodes if node['id'] == node_id), None)
                if node_info:
                    cluster_nodes.append(node_info)
            
            # Calculate average similarity score for the cluster
            for i in range(len(cycle)):
                source = cycle[i]
                target = cycle[(i + 1) % len(cycle)]
                
                # Find the link between these nodes
                for link in links:
                    if (link['source'] == source and link['target'] == target) or \
                       (link['source'] == target and link['target'] == source):
                        total_similarity += link['value']
                        link_count += 1
                        break
            
            avg_similarity = total_similarity / max(1, link_count)
            
            # Add cluster to the list
            clusters.append({
                'nodes': cluster_nodes,
                'avg_similarity': avg_similarity,
                'size': len(cluster_nodes)
            })
        
        # Sort clusters by size (descending) and then by average similarity (descending)
        clusters.sort(key=lambda x: (-x['size'], -x['avg_similarity']))
        
        # Remove duplicate clusters (those with the same set of nodes)
        unique_clusters = []
        seen_node_sets = set()
        
        for cluster in clusters:
            node_ids = frozenset(node['id'] for node in cluster['nodes'])
            if node_ids not in seen_node_sets:
                seen_node_sets.add(node_ids)
                unique_clusters.append(cluster)
        
        return unique_clusters

    def _generate_similarity_graph_html(self) -> str:
        """
        Generate HTML for the similarity graph visualization.
        
        Returns:
            str: HTML for the similarity graph section
        """

        self.logger.debug(f"_generate_similarity_graph_html() start.")

        similarity_threshold = self.min_similarity
        graph_data = self._generate_similarity_graph_data()
        
        if not graph_data['nodes'] or not graph_data['links']:
            return f'<div class="no-graph-data">No roles with similarity score ≥ {similarity_threshold} found.</div>'
        
        # Create a list of highly similar role pairs for quick navigation
        similar_pairs_html = ''
        for link in graph_data['links']:
            source_name = next((node['name'] for node in graph_data['nodes'] if node['id'] == link['source']), link['source'])
            target_name = next((node['name'] for node in graph_data['nodes'] if node['id'] == link['target']), link['target'])
            score = self._format_percentage(link['value'])
            score_value = link['value']
            
            similar_pairs_html += f'''
            <div class="similar-pair" 
                data-similarity="{score_value}" 
                data-source-name="{source_name.lower()}" 
                data-target-name="{target_name.lower()}"
                data-combined-names="{source_name.lower()} {target_name.lower()}">
                <span class="similarity-score {self._get_color_class(link['value'])}">{score}</span>
                <a href="javascript:void(0)" onclick="navigateToRole('{link['source']}', '{source_name}')" class="role-link" data-original-text="{source_name}">{source_name}</a> → 
                <a href="javascript:void(0)" onclick="navigateToRole('{link['target']}', '{target_name}')" class="role-link" data-original-text="{target_name}">{target_name}</a>
            </div>
            '''
        # Find similarity clusters (closed loops)
        clusters = self._find_similarity_clusters()
        
        # Generate HTML for similarity clusters
        clusters_html = ''
        if clusters:
            clusters_html = '''
            <div class="similarity-clusters">
                <h3>Similarity Clusters (Closed Loops)</h3>
                <div class="clusters-description">
                    <p>These clusters represent groups of roles that form closed loops of similarity relationships.</p>
                </div>
                <div class="clusters-filter-container">
                    <input type="text" id="clusters-filter" placeholder="Filter by role name..." class="clusters-filter">
                    <button onclick="clearClustersFilter()" class="clear-filter-button">Clear</button>
                </div>
                <table class="clusters-table">
                    <thead>
                        <tr>
                            <th>Cluster</th>
                            <th>Roles</th>
                            <th>Avg. Similarity</th>
                            <th>Size</th>
                        </tr>
                    </thead>
                    <tbody id="clusters-table-body">
            '''
            
            for i, cluster in enumerate(clusters):
                roles_html = ''
                first_node = cluster['nodes'][0] if cluster['nodes'] else None
                first_node_id = first_node['id'] if first_node else ''
                first_node_name = first_node['name'] if first_node else ''
                
                for node in cluster['nodes']:
                    roles_html += f'<a href="javascript:void(0)" onclick="navigateToRole(\'{node["id"]}\', \'{node["name"]}\')" class="role-link" data-original-text="{node["name"]}">{node["id"]}</a>, '
                roles_html = roles_html.rstrip(', ')
                
                avg_similarity = self._format_percentage(cluster['avg_similarity'])
                similarity_class = self._get_color_class(cluster['avg_similarity'])
                
                # Create a list of all node names for filtering
                node_names = [node["name"].lower() for node in cluster['nodes']]
                # Escape special characters in the node names to prevent HTML issues
                escaped_node_names = " ".join([name.replace('"', '&quot;') for name in node_names])
                
                clusters_html += f'''
                <tr class="cluster-row" data-cluster-index="{i+1}" data-node-names="{escaped_node_names}">
                    <td>
                        <div class="cluster-link-container" title="First node: {first_node_name}">
                            <a href="javascript:void(0)" onclick="highlightNodeInGraph('{first_node_id}', '{first_node_name}')" class="cluster-link">
                                Cluster {i+1}
                                <span class="cluster-first-node-indicator">→ {first_node_name}</span>
                            </a>
                        </div>
                    </td>
                    <td>{roles_html}</td>
                    <td class="{similarity_class}">{avg_similarity}</td>
                    <td>{cluster['size']}</td>
                </tr>
                '''
            
            clusters_html += '''
                    </tbody>
                </table>
            </div>
            '''
        self.logger.debug(f"_generate_similarity_graph_html() end.")
        return f'''
        <div class="similarity-graph-container">
         
            <div class="graph-container">
                <div class="stats-header">
                    <div class="stats-header-title">Similar Role Pairs (≥{similarity_threshold}%)</div>
                    
                </div>
                
               <div class="graph-content">
                    <div class="graph-controls">
                        <button onclick="toggleGraphView()">Show Graph</button>
                        <button onclick="toggleGraphHelp()" class="help-button">Help</button>
                        <button onclick="toggleClustersView()" class="clusters-button">Show Clusters</button>
                        <button onclick="resetGraphPositions()" class="reset-positions-button">Reset Positions</button>


                    </div>
                    
                    <div id="graph-help" class="graph-help hidden">
                        <p><strong>Graph Navigation:</strong></p>
                        <ul>
                            <li>Use the zoom controls (+/-) to zoom in and out</li>
                            <li>Click and drag nodes to reposition them</li>
                            <li>Click and drag the background to pan the view</li>
                            <li>Click on a node to navigate to that role's details</li>
                            <li>Hover over nodes to see similar roles with similarity scores</li>
                            <li>When hovering, connected links and nodes are highlighted</li>
                            <li>Full names of connected nodes are shown when hovering</li>
                            <li>Tooltips show outgoing connections (similar roles)</li>
                            <li>Nodes stay in place after dragging for easier organization</li>
                            <li>Use the "Reset Positions" button to rearrange all nodes</li>
                        </ul>
                        <button onclick="toggleGraphHelp()" class="close-help-button">Close Help</button>
                    </div>
                    
                    <div id="similarity-clusters" class="similarity-clusters-container hidden">
                        {clusters_html}
                        <button onclick="toggleClustersView()" class="close-clusters-button">Close Clusters</button>
                    </div>
                    
                    <div id="similarity-graph-canvas-container" class="hidden">
                        <canvas id="similarity-graph-canvas"></canvas>
                    </div>
                    
                    <div class="similar-pairs-list">
                        
                        <div class="similar-pairs-controls">
                            <div class="filter-container">
                                <input type="text" id="similar-pairs-filter" placeholder="Filter by role name..." class="similar-pairs-filter">
                                <button onclick="clearSimilarPairsFilter()" class="clear-filter-button">Clear</button>
                            </div>
                            <div class="sort-container">
                                <label for="similar-pairs-sort">Sort by:</label>
                                <select id="similar-pairs-sort" onchange="sortSimilarPairs(this.value)" class="similar-pairs-sort">
                                    <option value="similarity-desc">Similarity (High to Low)</option>
                                    <option value="similarity-asc">Similarity (Low to High)</option>
                                    <option value="name-asc">Role Name (A to Z)</option>
                                    <option value="name-desc">Role Name (Z to A)</option>
                                </select>
                            </div>
                        </div>
                        <div id="similar-pairs-container">
                        {similar_pairs_html}
                        </div>
                    </div>
               </div> <!-- graph content -->
                
                <script>
                    // Store graph data for rendering
                    const graphData = {graph_data};
                </script>
            </div><!-- graph content -->
        </div><!-- similarity graph container -->
        '''

    def _generate_html_report(self) -> str:
        """Generate complete HTML page for policy visualization."""
        self.logger.debug(f"_generate_html_report() start.")
        # Base HTML template with styles
        html_template = r'''<!DOCTYPE html>
                            <html lang="en">
                            <head>
                                <meta charset="UTF-8">
                                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                <title>Customr Roles Report</title>
                                <link rel="stylesheet" href="reports_styles.css">
                                <script src="https://cdnjs.cloudflare.com/ajax/libs/jsondiffpatch/0.4.1/jsondiffpatch.umd.min.js"></script>
                                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/jsondiffpatch/0.4.1/formatters-styles/html.css"/>
                                <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
                                <script src="reports.js"></script>
                            </head>
                            <body>
                                <div class="container">
                                    <div class="card">
                                        <div class="card-header">
                                            <h1 class="card-title">Custom Roles Report ({fetch_date})</h1>
                                        </div>
                                        <div class="summary-container">
                                            {account_policy_summary}
                                            {invalid_actions_html}
                                        </div>
                                        <div class="card-body">
                                            {role_cards}
                                        </div>
                                    </div>
                                </div>
                                <div class="floating-nav">
                                    <button class="nav-button" id="nav-top" title="Scroll to Top" onclick="scrollToTop()">
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                                            <path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/>
                                        </svg>
                                    </button>
                                    <button class="nav-button" id="nav-bottom" title="Scroll to Bottom" onclick="scrollToBottom()">
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                                            <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/>
                                        </svg>
                                    </button>
                                </div>
                            </body>
                            </html>'''

        # Generate role cards
        role_cards_html = ""
        for role_key, similar_roles in self.policy_data.items():
            role_cards_html += self._generate_role_card_html(role_key, similar_roles)
        
        # Generate account policy summary
        account_policy_summary = self._generate_summary_statistics()
        
         # Add invalid actions section after summary statistics if available
        if self.invalid_actions:
            invalid_actions_html = self._generate_invalid_actions_section()
        else:
            invalid_actions_html = ""
               
        self.logger.debug(f"_generate_html_report() account_policy_summary: {account_policy_summary}")
        self.logger.debug(f"_generate_html_report() role_cards_html: {role_cards_html}")
        self.logger.debug(f"_generate_html_report() invalid_actions_html: {invalid_actions_html}")

        # Replace placeholders in template
        html_content = html_template.format(
            fetch_date=self.ldc_cache_data.get("fetch_date", "Unknown Date"),
            account_policy_summary=account_policy_summary,
            role_cards=role_cards_html,
            invalid_actions_html=invalid_actions_html
        )
        
        self.logger.debug(f"_generate_html_report() end.")

        return html_content
    

    def _generate_summary_statistics(self) -> str:
        """Generate HTML for the account policy summary."""
        self.logger.debug(f"_generate_summary_statistics() start")

        total_policies = self.ldc_cache_data['total_roles']
        total_assigned_teams = self.ldc_cache_data['total_assigned_teams']
        total_assigned_members = self.ldc_cache_data['total_assigned_members']
        total_unassigned_roles = self.ldc_cache_data['total_unassigned_roles']
        total_assigned_roles = self.ldc_cache_data['total_assigned_roles']

        list_assigned_teams = self.ldc_cache_data['assigned_teams']
        list_assigned_teams_li = "\n".join([f"<li>{team}</li>" for team in list_assigned_teams if team])

        list_assigned_members =  self.ldc_cache_data['assigned_members']
        list_assigned_members_li = "\n".join([f"<li>{member}</li>" for member in list_assigned_members if member])

        list_unassigned_roles = self.ldc_cache_data['unassigned_roles']
        list_unassigned_roles_li = "\n".join([f"<li>{role}</li>" for role in list_unassigned_roles if role])

        list_assigned_roles = self.ldc_cache_data['assigned_roles']
        list_assigned_roles_li = "\n".join([f"<li>{role}</li>" for role in list_assigned_roles if role])
        self.logger.debug(f"_generate_summary_statistics() end")

        # Generate teams with project access table
        teams_project_table = self._generate_teams_project_table()
        invalid_actions_len = len(self.invalid_actions) if self.invalid_actions is not None else 0

        similarity_graph = self._generate_similarity_graph_html()

        return f'''
        <div class="statistics-card collapsed">
            <div class="stats-header">
                <h4 class="stats-header-title">Account Policy Summary</h4>  
                <button onclick="toggleStatisticsCard(this)" class="toggle-statistics-button">Expand</button>
            </div>
            <div class="stats-content">
            <div class="stats-body">
                <div class="stat-item">
                    <div class="stat-item-row">
                        <div class="stat-label">Total Policies</div>
                        <div class="stat-value-static">{total_policies}</div>
                    </div>
                    <div class="stat-item-row">
                        <div class="stat-label">Total Teams</div>
                        <div class="stat-value-static">{self.ldc_cache_data['total_teams']}</div>
                    </div>
                    <div class="stat-item-row">
                        <div class="stat-label">Total Members</div>
                        <div class="stat-value-static">{self.ldc_cache_data['total_account_members']}</div>
                    </div>
                    <div class="stat-item-row">
                        <div class="stat-label">Total Roles with Invalid Actions</div>
                        <div class="stat-value-static {self._get_value_class_bad_good(invalid_actions_len)}">{invalid_actions_len}</div>
                    </div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Teams With Roles</div>
                    <div class="stat-value" onclick="toggleSummaryDetailPanel('account-summary')">{total_assigned_teams}</div>
                    <div id="account-summary" class="detail-panel teams-assigned-roles-panel hidden">
                        <div class="detail-header">
                            <h4>Teams With Roles</h4>
                            <button class="close-button" onclick="toggleSummaryDetailPanel('account-summary')">×</button>
                        </div>
                        <ul class="detail-list">
                            {list_assigned_teams_li or "<li>No teams assigned</li>"}
                        </ul>
                    </div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Members With Roles</div>
                    <div class="stat-value" onclick="toggleSummaryDetailPanel('account-summary')">{total_assigned_members}</div>
                    <div id="account-summary" class="detail-panel member-assigned-roles-panel hidden">
                        <div class="detail-header">
                            <h4>Member with Roles</h4>
                            <button class="close-button" onclick="toggleSummaryDetailPanel('account-summary')">×</button>
                        </div>
                        <ul class="detail-list">
                            {list_assigned_members_li or "<li>No member assigned</li>"}
                        </ul>
                    </div>
                </div>

                <div class="stat-item">
                    <div class="stat-label">Assigned Roes</div>
                    <div class="stat-value {self._get_percent_value_class(total_assigned_roles/ total_policies*100)}" onclick="toggleSummaryDetailPanel('account-summary')">{total_assigned_roles}({self._format_percentage(total_assigned_roles/ total_policies)})</div>
                    <div id="account-summary" class="detail-panel assigned-roles-panel hidden">
                        <div class="detail-header">
                            <h4>Assigned Roles</h4>
                            <button class="close-button" onclick="toggleSummaryDetailPanel('account-summary')">×</button>
                        </div>
                        <ul class="detail-list">
                            {list_assigned_roles_li or "<li>No assigned roles</li>"}
                        </ul>
                    </div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Not Assigned</div>
                    <div class="stat-value {self._get_percent_value_class(total_unassigned_roles/ total_policies*100, inverse=True)}" onclick="toggleSummaryDetailPanel('account-summary')">{total_unassigned_roles}({self._format_percentage(total_unassigned_roles/ total_policies)})</div>
                    <div id="account-summary" class="detail-panel unassigned-roles-panel hidden">
                        <div class="detail-header">
                            <h4>Unassigned Roles</h4>
                            <button class="close-button" onclick="toggleSummaryDetailPanel('account-summary')">×</button>
                        </div>
                        <ul class="detail-list">
                            {list_unassigned_roles_li or "<li>No unassigned roles</li>"}
                        </ul>
                    </div>
                </div>
                </div>
                {similarity_graph}
            </div>
        </div>
        
        <div class="statistics-card">
            <div class="stats-header">
                <h4 class="stats-header-title">Teams Project Access</h4>
                <button onclick="toggleTeamsTable(this)" class="toggle-statistics-button">Expand</button>
            </div>
            <div class="stats-content">

                    <div id="teams-project-table" class="teams-project-stats-body teams-project-table hidden">
                        <p>The following table shows the teams with roles that have write access to each project.</p>
                        {teams_project_table}
                    </div>

            </div>
        </div>
        ''' 
    
    def _generate_teams_project_table(self) -> str:
        """Generate HTML table for teams with project access using div layout."""
        self.logger.debug(f"_generate_teams_project_table() start.")
        team_project_list = self.ldc_cache_data.get('team_project_list', {})
        
        table_rows = []
        for team_key, team_data in team_project_list.items():
            projects = team_data.get('projects', [])
            has_roles = team_data.get('has_roles', False)
            roles = team_data.get('roles', [])
            total_projects = team_data.get('total_projects_write_access', 0)
            
            if len(projects) == 0:
                continue
            
            project_cells = []
            for project_key in projects:
                project_cells.append(f'''
                    <div class="project-item-pill">
                        <span class="project-key">{project_key}</span>
                    </div>
                ''')
            role_pills=[]
            for role in roles:
                role_pills.append(f'''
                    <div class="team-role-pill" onclick="navigateToRole('{role}', '{role}')">
                        {role}
                    </div>
                ''')
            role_status = 'has-roles' if has_roles else 'no-roles'
            role_count = len(roles) if roles else 0
            
            table_rows.append(f'''
                <div class="table-row">
                    <div class="table-cell team-cell">
                        <div class="team-name">{team_key} ({role_count} roles)</div>
                        <div class="team-role-container">
                            
                            {"".join(role_pills) if role_pills else "No roles"}
                        </div>
                    </div>
                    <div class="table-cell projects-cell">
                        {"".join(project_cells) if project_cells else "No projects"}
                    </div>
                </div>
            ''')
        self.logger.debug(f"_generate_teams_project_table() end.")
        return f'''
            <div class="teams-project-table-content">
                <div class="table-header">
                    <div class="header-cell">Team</div>
                    <div class="header-cell">Projects</div>
                </div>
                <div class="table-body">
                    {"".join(table_rows)}
                </div>
            </div>
        '''

    def _generate_role_card_html(self, role_key: str, similar_roles: Dict) -> str:
        """Generate HTML for a single role card."""
            # Determine role type and icon background
        role_type = self._determine_role_type(role_key)

        role_info = self._getRoleInfo(role_key)
        role_name = role_info['name'] if role_info else 'Not defined'

        return f'''
            <div id="role-{role_key}" class="role-card">
                 <div class="role-icon role-type-{role_type}">
                        {role_name[0].upper()}
                </div>
                <div class="role-info">
                    <div class="role-title">
                        {role_name}
                        <span class="role-tag">{role_type}</span>
                        
                    </div>
                    {self._generate_policy_detail_html(role_info, role_key)}
                
                    <div class="similar-roles-section">
                        <div class="similar-roles">
                            <div class="similar-roles-title">Similar Roles</div>
                            {self._generate_similar_roles_html(role_key, similar_roles)}
                        </div>
                        <div class="similar-policies-section">
                            {self._generate_similar_roles_policy_html(role_key, similar_roles, role_info)}
                        </div>
                    </div>
                </div>
            </div>
            '''
    
    def _determine_role_type(self, role_key: str) -> str:
        """Determine the type of role based on its key."""
        role_key_lower = role_key.lower()
        if role_key_lower == "owner":
            return "owner"
        elif role_key_lower == "admin":
            return "admin"
        elif role_key_lower == "writer":
            return "writer"
        return "custom"


    def _create_invalid_action_pill(self, actions: str) -> str:
        html_pill = ""
        
        for action in actions:
            html_pill += f'<span class="invalid-action-pill">{action}</span>'
        return html_pill
    
    def _create_invalid_action_roles(self) -> str:
        self.logger.debug(f"_create_invalid_action_roles() start.")
        self.logger.debug(f"_create_invalid_action_roles() invalid_actions={self.invalid_actions}")

        html_roles = ""

        for role_key, actions in self.invalid_actions.items():
        
            
            actions_data = " ".join(actions).lower()
            
            
            self.logger.debug(f"role_key [{role_key}] actions [{actions_data}]")

            role_info = self._getRoleInfo(role_key)
            role_name = role_info.get('name', role_key)
            
            
            html_roles += f"""
            <div class="invalid-action-item" data-role-name="{role_name.lower()}" data-actions="{actions_data}">
                <div class="invalid-action-role">
                    <a href="#role-{role_key}" class="role-link">{role_name}</a>
                </div>
                <div class="invalid-action-items">
                    {self._create_invalid_action_pill(actions)}
                </div>
            </div>
            """
        return html_roles
            
    def _generate_invalid_actions_section(self) -> str:
        """
        Generate HTML for the invalid actions section.
        
        This method creates an HTML section that displays roles with invalid actions.
        Each invalid action is displayed as a pill, similar to the similar-role-pill style.
        The section includes a filter input for searching by role name or action.
        
        Args:
            invalid_actions: Dictionary mapping role keys to lists of invalid actions
            
        Returns:
            HTML string for the invalid actions section
            
        Note:
            If the invalid_actions dictionary is empty, an empty string is returned.
        """
        self.logger.debug(f"_generate_invalid_actions_section() start.")
        if not self.invalid_actions:
            return ""
        
        html_template = r"""
        <div class="statistics-card collapsed">
            <div class="stats-header">
                <h4 class="stats-header-title">Roles with Invalid Actions <a href="https://launchdarkly.com/docs/home/account/role-actions" target="_blank">(docs)</a></h4> 
                <button class="toggle-statistics-button" onclick="toggleStatisticsCard(this)">  Expand  </button>
            </div>
            <div class="stats-content">
                <div class="invalid-actions-stats-body">
                    <p>The following roles contain actions that are not recognized in the LaunchDarkly API. These may be deprecated or misspelled.</p>
                    
                    <div class="invalid-actions-filter-container">
                        <input type="text" id="invalid-actions-filter" placeholder="Filter by role or action..." class="invalid-actions-filter">
                        <button onclick="clearInvalidActionsFilter()" class="clear-invalid-actions-filter-button">Clear</button>
                    </div>
                    
                    <div class="invalid-actions-list">
                        <div class="invalid-actions-header">
                            <div class="invalid-actions-role-header">Role</div>
                            <div class="invalid-actions-items-header">Invalid Actions</div>
                        </div>
                        <div id="invalid-actions-container">
                        {invalid_action_roles_html}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """
        self.logger.debug(f"_generate_invalid_actions_section() end.")
        return html_template.format(invalid_action_roles_html=self._create_invalid_action_roles())
        

