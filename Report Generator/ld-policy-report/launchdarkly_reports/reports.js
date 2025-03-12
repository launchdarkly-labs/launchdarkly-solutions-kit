document.addEventListener('DOMContentLoaded', function() {

    document.querySelectorAll('.expand-toggle').forEach(toggle => {
        toggle.addEventListener('click', function() {
            const preview = this.nextElementSibling;
            preview.classList.toggle('expanded');
            this.classList.toggle('expanded');
            this.innerHTML = preview.classList.contains('expanded') 
                ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7.41 15.41L12 10.83L16.59 15.41L18 14L12 8L6 14L7.41 15.41Z" fill="#0075FF"></path></svg>Hide Policy'
                : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16.59 8.59L12 13.17L7.41 8.59L6 10L12 16L18 10L16.59 8.59Z" fill="#0075FF"></path></svg>Show Policy';
        });
    });

    // Initialize the similarity graph if it exists
    initSimilarityGraph();
    
    // Initialize similar pairs filter and sorting
    const filterInput = document.getElementById('similar-pairs-filter');
    if (filterInput) {
        filterInput.addEventListener('input', function() {
            filterSimilarPairs(this.value);
        });
    }
    
    // Initialize clusters filter
    const clustersFilterInput = document.getElementById('clusters-filter');
    if (clustersFilterInput) {
        clustersFilterInput.addEventListener('input', function() {
            filterClusters(this.value);
        });
    }
    
    // Initialize sorting (default: similarity-desc)
    const sortSelect = document.getElementById('similar-pairs-sort');
    if (sortSelect) {
        // Set default sort order
        sortSelect.value = 'similarity-desc';
        // Initial sort
        sortSimilarPairs('similarity-desc');
    }
    
    // Initialize button text based on content visibility
    initializeButtonText();
});

// Global variable to store node to cluster mapping
let nodeToCluster = {};

function initSimilarityGraph() {
    
    // console.log(`${graphData}`);
    if (typeof graphData !== 'undefined' && graphData.nodes.length > 0) {
        renderForceGraph();
    }
}

function renderForceGraph() {
    const container = document.getElementById('similarity-graph-canvas-container');
    if (!container) return;
    
    // Clear any existing content
    container.innerHTML = '';
    
    // Create SVG element
    const width = container.clientWidth;
    const height = 500;
    
    const svg = d3.create('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', [0, 0, width, height])
        .attr('style', 'max-width: 100%; height: auto;');
    
    // Add a group for the entire graph that will be transformed during zoom
    const g = svg.append('g')
        .attr('class', 'graph-container');
    
    // Define color scale for node types
    const color = d3.scaleOrdinal()
        .domain(['admin', 'writer', 'reader', 'custom'])
        .range(['#FF5252', '#2196F3', '#4CAF50', '#FFC107']);
    
    // Create tooltip
    const tooltip = d3.select('body').append('div')
        .attr('class', 'graph-tooltip')
        .style('opacity', 0);
    
    // Set initial positions for nodes in a grid or circle layout if they don't have positions yet
    const nodeCount = graphData.nodes.length;
    if (nodeCount > 0) {
        // Check if nodes already have positions
        const hasPositions = graphData.nodes.some(node => node.x !== undefined && node.y !== undefined);
        
        if (!hasPositions) {
            // Determine if we should use a grid or circle layout based on node count
            if (nodeCount <= 20) {
                // Circle layout for fewer nodes
                const radius = Math.min(width, height) * 0.35;
                graphData.nodes.forEach((node, i) => {
                    const angle = (i / nodeCount) * 2 * Math.PI;
                    node.x = width / 2 + radius * Math.cos(angle);
                    node.y = height / 2 + radius * Math.sin(angle);
                });
            } else {
                // Grid layout for more nodes
                const cols = Math.ceil(Math.sqrt(nodeCount));
                const rows = Math.ceil(nodeCount / cols);
                const cellWidth = width / (cols + 1);
                const cellHeight = height / (rows + 1);
                
                graphData.nodes.forEach((node, i) => {
                    const col = i % cols;
                    const row = Math.floor(i / cols);
                    node.x = cellWidth * (col + 1);
                    node.y = cellHeight * (row + 1);
                });
            }
        }
    }
    
    // Create the force simulation
    const simulation = d3.forceSimulation(graphData.nodes)
        .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(40))
        .force('x', d3.forceX(width / 2).strength(0.1))
        .force('y', d3.forceY(height / 2).strength(0.1))
        .alphaDecay(0.05)  // Faster cooling
        .velocityDecay(0.4);  // More friction to slow down movement
    
    // Detect closed loops (similarity clusters)
    const clusters = detectSimilarityClusters(graphData);
    
    // Create a map of node IDs to their cluster index
    nodeToCluster = {}; // Reset the global variable
    clusters.forEach((cluster, index) => {
        cluster.nodeIds.forEach(nodeId => {
            nodeToCluster[nodeId] = index;
        });
    });
    
    // Create links
    const link = g.append('g')
        .attr('class', 'links')
        .attr('stroke', '#999')
        .attr('stroke-opacity', 0.6)
        .selectAll('line')
        .data(graphData.links)
        .join('line')
        .attr('stroke-width', d => Math.max(1, d.value * 3))
        .attr('stroke', d => {
            // Check if both nodes are in the same cluster
            const sourceCluster = nodeToCluster[d.source];
            const targetCluster = nodeToCluster[d.target];
            
            if (sourceCluster !== undefined && sourceCluster === targetCluster) {
                // Use a distinct color for each cluster
                const clusterColors = ['#E91E63', '#9C27B0', '#673AB7', '#3F51B5', '#2196F3', '#009688', '#4CAF50', '#CDDC39'];
                return clusterColors[sourceCluster % clusterColors.length];
            }
            
            // Default coloring based on similarity score
            if (d.value >= 0.95) return '#4CAF50';
            if (d.value >= 0.8) return '#FFC107';
            return '#FF5252';
        });
    
    // Create nodes
    const node = g.append('g')
        .attr('class', 'nodes')
        .selectAll('.node')
        .data(graphData.nodes)
        .join('g')
        .attr('class', 'node')
        .call(drag(simulation));
    
    // Add circles to nodes
    node.append('circle')
        .attr('r', d => {
            // Make nodes in clusters slightly larger
            return nodeToCluster[d.id] !== undefined ? 24 : 20;
        })
        .attr('data-id', d => d.id)
        .attr('fill', d => {
            // If node is part of a cluster, use a distinct color
            const clusterIndex = nodeToCluster[d.id];
            if (clusterIndex !== undefined) {
                const clusterColors = ['#E91E63', '#9C27B0', '#673AB7', '#3F51B5', '#2196F3', '#009688', '#4CAF50', '#CDDC39'];
                return clusterColors[clusterIndex % clusterColors.length];
            }
            return color(d.type);
        })
        .attr('stroke', '#fff')
        .attr('stroke-width', d => nodeToCluster[d.id] !== undefined ? 2.5 : 1.5);
    
    // Add text labels to nodes
    node.append('text')
        .text(d => d.name.substring(0, 10) + (d.name.length > 10 ? '...' : ''))
        .attr('x', 0)
        .attr('y', 30)
        .attr('text-anchor', 'middle')
        .attr('fill', '#333')
        .attr('font-size', '10px');
    
    // Add hover effects
    node.on('mouseover', function(event, d) {
        // Find all connected nodes and their similarity scores
        const connections = [];
        const connectedLinks = [];
        const connectedNodes = [];
        const processedNodeIds = new Set(); // Track processed nodes to avoid duplicates
        const nodeConnections = new Map(); // Map to track highest similarity for each connected node
        
        graphData.links.forEach(link => {
            // Check if this node is the source or target of the link
            if (link.source.id === d.id || (typeof link.source === 'string' && link.source === d.id)) {
                // This node is the source, so the target is connected
                const targetNode = typeof link.target === 'object' ? link.target : 
                    graphData.nodes.find(n => n.id === link.target);
                if (targetNode) {
                    connectedLinks.push(link);
                    connectedNodes.push(targetNode.id);
                    
                    // Update the node connection with highest similarity score
                    if (!nodeConnections.has(targetNode.id) || 
                        nodeConnections.get(targetNode.id).similarity < link.value) {
                        nodeConnections.set(targetNode.id, {
                            node: targetNode,
                            similarity: link.value,
                            direction: 'outgoing'
                        });
                    }
                }
            } else if (link.target.id === d.id || (typeof link.target === 'string' && link.target === d.id)) {
                // This node is the target, so the source is connected
                const sourceNode = typeof link.source === 'object' ? link.source : 
                    graphData.nodes.find(n => n.id === link.source);
                if (sourceNode) {
                    connectedLinks.push(link);
                    connectedNodes.push(sourceNode.id);
                    
                    // Update the node connection with highest similarity score
                    if (!nodeConnections.has(sourceNode.id) || 
                        nodeConnections.get(sourceNode.id).similarity < link.value) {
                        nodeConnections.set(sourceNode.id, {
                            node: sourceNode,
                            similarity: link.value,
                            direction: 'incoming'
                        });
                    }
                }
            }
        });
        
        // Convert the Map to an array of connections
        const uniqueConnections = Array.from(nodeConnections.values())
            // Filter to only include outgoing connections
            .filter(conn => conn.direction === 'outgoing');
        
        // Highlight connected links
        link.attr('stroke-opacity', l => {
            const isConnected = connectedLinks.includes(l);
            return isConnected ? 1 : 0.2;
        }).attr('stroke-width', l => {
            const isConnected = connectedLinks.includes(l);
            return isConnected ? Math.max(2, l.value * 4) : Math.max(1, l.value * 3);
        });
        
        // Highlight connected nodes and show full names
        node.select('circle').attr('stroke-width', n => {
            if (n.id === d.id) return 3; // Current node
            return connectedNodes.includes(n.id) ? 3 : 1.5; // Connected vs non-connected
        });
        
        // Show full names for connected nodes
        node.select('text')
            .text(n => {
                if (n.id === d.id || connectedNodes.includes(n.id)) {
                    return n.name; // Show full name for hovered and connected nodes
                } else {
                    return n.name.substring(0, 10) + (n.name.length > 10 ? '...' : '');
                }
            })
            .attr('font-weight', n => {
                return (n.id === d.id || connectedNodes.includes(n.id)) ? 'bold' : 'normal';
            });
        
        // Sort connections by similarity score (descending)
        uniqueConnections.sort((a, b) => b.similarity - a.similarity);
        
        // Build the tooltip content
        let tooltipContent = `
            <strong>${d.name}</strong><br/>
            Type: ${d.type}<br/>
        `;
        
        // Add cluster information if node is part of a cluster
        const clusterIndex = nodeToCluster[d.id];
        if (clusterIndex !== undefined) {
            tooltipContent += `<strong>Part of Cluster ${clusterIndex + 1}</strong><br/>`;
        }
        
        // Add connected nodes with similarity scores
        if (uniqueConnections.length > 0) {
            tooltipContent += `<strong>Similar Roles:</strong><br/>`;
            tooltipContent += `<div class="tooltip-connections">`;
            uniqueConnections.forEach(conn => {
                const similarityClass = conn.similarity >= 0.95 ? 'high' : 
                                        conn.similarity >= 0.8 ? 'medium' : 'low';
                const similarityPercent = Math.round(conn.similarity * 100) + '%';
                tooltipContent += `
                    <div class="tooltip-connection">
                        <span class="similarity-score ${similarityClass}">${similarityPercent}</span>
                        <a href="javascript:void(0)" onclick="navigateToRole('${conn.node.id}', '${conn.node.name}')" class="role-link">${conn.node.name}</a>
                    </div>
                `;
            });
            tooltipContent += `</div>`;
        }
        
        tooltipContent += `<a href="javascript:void(0)" onclick="navigateToRole('${d.id}', '${d.name}')" class="tooltip-goto">Go to role details</a>`;
        
        tooltip.transition()
            .duration(200)
            .style('opacity', .9);
        
        tooltip.html(tooltipContent)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 28) + 'px');
    })
    .on('mouseout', function() {
        // Reset link opacity and width
        link.attr('stroke-opacity', 0.6)
            .attr('stroke-width', d => Math.max(1, d.value * 3));
        
        // Reset node stroke width
        node.select('circle')
            .attr('stroke-width', d => nodeToCluster[d.id] !== undefined ? 2.5 : 1.5);
        
        // Reset node text
        node.select('text')
            .text(d => d.name.substring(0, 10) + (d.name.length > 10 ? '...' : ''))
            .attr('font-weight', 'normal');
        
        tooltip.transition()
            .duration(500)
            .style('opacity', 0);
    })
    .on('click', function(event, d) {
        // Navigate to the role card using the navigateToRole function
        navigateToRole(d.id, d.name);
    });
    
    // Define zoom behavior
    const zoom = d3.zoom()
        .scaleExtent([0.1, 4]) // Set min/max zoom scale
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
            
            // Update the zoom level display
            const zoomLevel = Math.round(event.transform.k * 100);
            document.getElementById('zoom-level').textContent = `${zoomLevel}%`;
        });
    
    // Apply zoom behavior to SVG
    svg.call(zoom);
    
    // Add zoom controls to the container
    const zoomControls = document.createElement('div');
    zoomControls.className = 'zoom-controls';
    zoomControls.innerHTML = `
        <button id="zoom-in" title="Zoom In">+</button>
        <span id="zoom-level">100%</span>
        <button id="zoom-out" title="Zoom Out">-</button>
        <button id="zoom-reset" title="Reset Zoom">Reset</button>
    `;
    container.appendChild(zoomControls);
    
    // Add event listeners for zoom controls
    document.getElementById('zoom-in').addEventListener('click', () => {
        svg.transition().duration(300).call(zoom.scaleBy, 1.3);
    });
    
    document.getElementById('zoom-out').addEventListener('click', () => {
        svg.transition().duration(300).call(zoom.scaleBy, 0.7);
    });
    
    document.getElementById('zoom-reset').addEventListener('click', () => {
        svg.transition().duration(300).call(
            zoom.transform,
            d3.zoomIdentity.translate(width / 2, height / 2).scale(1).translate(-width / 2, -height / 2)
        );
    });
    
    // Update positions on each tick
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        node.attr('transform', d => `translate(${d.x},${d.y})`);
    });
    
    // Append the SVG to the container
    container.appendChild(svg.node());
    
    // Drag function for nodes
    function drag(simulation) {
        function dragstarted(event) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }
        
        function dragged(event) {
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }
        
        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            // Keep the node fixed at its final position instead of releasing it
            // event.subject.fx = null;
            // event.subject.fy = null;
        }
        
        return d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended);
    }
    
    // Function to detect similarity clusters (closed loops)
    function detectSimilarityClusters(graphData) {
        const nodes = graphData.nodes;
        const links = graphData.links;
        
        // Create an adjacency list representation of the graph
        const adjacencyList = {};
        nodes.forEach(node => {
            adjacencyList[node.id] = [];
        });
        
        links.forEach(link => {
            const source = typeof link.source === 'object' ? link.source.id : link.source;
            const target = typeof link.target === 'object' ? link.target.id : link.target;
            
            adjacencyList[source].push(target);
        });
        
        // Find strongly connected components (Tarjan's algorithm)
        // https://www.geeksforgeeks.org/tarjan-algorithm-find-strongly-connected-components/
        const clusters = [];
        const visited = new Set();
        const stack = [];
        const onStack = new Set();
        const ids = {};
        const lowLinks = {};
        let id = 0;
        
        function strongConnect(node) {
            ids[node] = lowLinks[node] = id++;
            stack.push(node);
            onStack.add(node);
            visited.add(node);
            
            for (const neighbor of adjacencyList[node]) {
                if (!visited.has(neighbor)) {
                    strongConnect(neighbor);
                    lowLinks[node] = Math.min(lowLinks[node], lowLinks[neighbor]);
                } else if (onStack.has(neighbor)) {
                    lowLinks[node] = Math.min(lowLinks[node], ids[neighbor]);
                }
            }
            
            if (ids[node] === lowLinks[node]) {
                const component = [];
                let w;
                do {
                    w = stack.pop();
                    onStack.delete(w);
                    component.push(w);
                } while (w !== node);
                
                //  if (component.length >= 2) {
                if (component.length > 2) {
                    clusters.push({
                        nodeIds: component,
                        size: component.length
                    });
                }
            }
        }
        
        // Run the algorithm for each unvisited node
        for (const node of Object.keys(adjacencyList)) {
            if (!visited.has(node)) {
                strongConnect(node);
            }
        }
        
        // Sort clusters by size (descending)
        clusters.sort((a, b) => b.size - a.size);
        
        return clusters;
    }
}

function toggleGraphView() {
    const container = document.getElementById('similarity-graph-canvas-container');
    const button = document.querySelector('button[onclick="toggleGraphView()"]');
    
    if (container) {
        container.classList.toggle('hidden');
        
        // Update button text based on visibility
        if (button) {
            button.textContent = container.classList.contains('hidden') ? 'Show Graph' : 'Hide Graph';
        }
        
        if (!container.classList.contains('hidden')) {
            // Re-render the graph when showing it
            renderForceGraph();
        }
    }
}

function toggleGraphHelp() {
    const helpSection = document.getElementById('graph-help');
    if (helpSection) {
        helpSection.classList.toggle('hidden');
    }
}

function toggleClustersView() {
    const clustersSection = document.getElementById('similarity-clusters');
    const showButton = document.querySelector('.clusters-button');
    const closeButton = document.querySelector('.close-clusters-button');
    
    if (clustersSection) {
        clustersSection.classList.toggle('hidden');
        
        // Update button text based on visibility
        if (showButton) {
            showButton.textContent = clustersSection.classList.contains('hidden') ? 'Show Clusters' : 'Hide Clusters';
        }
        
        // Also update the close button at the bottom of clusters view if it exists
        if (closeButton) {
            closeButton.textContent = 'Close Clusters';
        }
    }
}

function resetGraphPositions() {
    // Clear any fixed positions from nodes
    if (typeof graphData !== 'undefined' && graphData.nodes) {
        graphData.nodes.forEach(node => {
            node.fx = null;
            node.fy = null;
        });
    }
    
    // Re-render the graph
    renderForceGraph();
}

function togglePolicy(id) {
    const policyElement = document.getElementById(`${id}`);
    if (policyElement) {
        const thisPolicy = document.querySelector(`#${id}-this-policy>pre`).innerText;
        const thatPolicy= document.querySelector(`#${id}-that-policy>pre`).innerText;
        const diffContainer = document.querySelector(`#${id}-diff-container`);
        const annotatedContainer = document.querySelector(`#${id}-diff-annotated-container`);

        compareJSON({diffContainer, annotatedContainer,  left:JSON.parse(thisPolicy), right:JSON.parse(thatPolicy)});
        policyElement.classList.toggle('show');
    }
}
                                
function toggleDetailPanel(panelId) {
    const panel = document.getElementById(panelId);
    if (panel) {
        panel.classList.toggle('hidden');
    }
}

function toggleSummaryDetailPanel(panelId) {
    const panels = document.querySelectorAll(`#${panelId}`);
    
    panels?.forEach(panel => {
        panel.classList.toggle('hidden');
    });

}

function compareJSON({diffContainer, annotatedContainer, left, right}) {
    try {

        var delta = jsondiffpatch.diff(left, right);
        

        if (!delta) {
            diffContainer.innerHTML = "<p>No differences found.</p>";
            return;
        }
        diffContainer.innerHTML = jsondiffpatch.formatters.html.format(delta, left);
        annotatedContainer.innerHTML = jsondiffpatch.formatters.annotated.format(delta, left);

     
    } catch (e) {
        alert("Invalid JSON input. Please check your JSON format.");
    }
}



// Scroll to top function
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// Scroll to bottom function
function scrollToBottom() {
    window.scrollTo({
        top: document.body.scrollHeight,
        behavior: 'smooth'
    });
}

window.addEventListener('scroll', function() {
    
    const floatingNav = document.querySelector('.floating-nav');
    
    // Show nav when scrolled down a bit
    if (window.scrollY > 300) {
        floatingNav?.classList.remove('hidden');
    } else {
        floatingNav?.classList.add('hidden');
    }
});

// Initialize nav visibility
document.addEventListener('DOMContentLoaded', function() {
    const floatingNav = document.querySelector('.floating-nav');
    if (window.scrollY <= 300) {
        floatingNav.classList.add('hidden');
    }
});

function toggleAnnotatedDiff(containerId) {
    const container = document.getElementById(containerId);
    const button = container.previousElementSibling;
    
    if (container) {
        container.classList.toggle('hidden');
        // Update button text based on visibility
        button.textContent = container.classList.contains('hidden') 
            ? 'Show Annotated Diff' 
            : 'Hide Annotated Diff';
    }
}

function toggleSimilarityGraphContainer() {
    const container = document.querySelector('.similarity-graph-container');
    if (container) {
        container.classList.toggle('collapsed');
        
        // Update button text
        const button = document.querySelector('.toggle-graph-container-button');
        if (button) {
            button.textContent = container.classList.contains('collapsed') 
                ? 'Expand' 
                : 'Collapse';
        }
    }
}

function toggleStatisticsCard(buttonElement) {
    // Find the parent statistics-card
    const card = buttonElement.closest('.statistics-card');
    

    if (card) {
        card.classList.toggle('collapsed');

        // Update button text
        buttonElement.textContent = card.classList.contains('collapsed') 
            ? 'Expand' 
            : 'Collapse';
    }
}

function toggleTeamsTable(buttonElement) {
    // Find the parent statistics-card
    const table = document.getElementById('teams-project-table');
    
    
    if (table) {
        table.classList.toggle('hidden');

        // Update button text
        buttonElement.textContent = table.classList.contains('collapsed') 
            ? 'Expand' 
            : 'Collapse';
    }
}

function navigateToRole(roleId, roleName) {
    const roleElement = document.getElementById(`role-${roleId}`);
    if (roleElement) {
        roleElement.scrollIntoView({
            behavior: 'smooth'
        });
        
        // Highlight the role card briefly
        roleElement.classList.add('highlight-role');
        setTimeout(() => {
            roleElement.classList.remove('highlight-role');
        }, 2000);
    } else {
        console.warn(`Could not find element with ID: role-${roleId}`);
        // Show a notification to the user
        const notification = document.createElement('div');
        notification.className = 'graph-notification';
        notification.textContent = `Could not find role details for: ${roleName}`;
        
        document.body.appendChild(notification);
        
        // Remove the notification after a few seconds
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 500);
        }, 3000);
    }
}

function highlightNodeInGraph(nodeId, nodeName) {
    // Make sure the graph is visible
    const container = document.getElementById('similarity-graph-canvas-container');
    if (container && container.classList.contains('hidden')) {
        toggleGraphView(); // Show the graph if it's hidden
    }
    
    // Close the clusters view if it's open
    const clustersSection = document.getElementById('similarity-clusters');
    if (clustersSection && !clustersSection.classList.contains('hidden')) {
        toggleClustersView(); // Hide the clusters view
    }
    
    // Find the node in the graph
    if (typeof graphData !== 'undefined' && graphData.nodes) {
        const node = graphData.nodes.find(n => n.id === nodeId);
        if (node) {
            // Get the SVG and its dimensions
            const svg = d3.select('#similarity-graph-canvas-container svg');
            const width = svg.attr('width');
            const height = svg.attr('height');
            
            // Center the view on the node
            const transform = d3.zoomTransform(svg.node());
            const scale = transform.k;
            const x = -node.x * scale + width / 2;
            const y = -node.y * scale + height / 2;
            
            // Apply the transform
            svg.transition()
                .duration(750)
                .call(
                    d3.zoom().transform,
                    d3.zoomIdentity.translate(x, y).scale(scale)
                );
            
            // Remove any existing highlighted-node class
            svg.selectAll('.node circle').classed('highlighted-node', false);
            
            // Highlight the node
            const nodeElement = svg.select(`.node circle[data-id="${nodeId}"]`);
            if (nodeElement.size() > 0) {
                // Flash the node with a more prominent effect
                nodeElement
                    .classed('highlighted-node', true)
                    .transition()
                    .duration(300)
                    .attr('r', 35)
                    .attr('stroke-width', 5)
                    .attr('stroke', '#FF5252')
                    .transition()
                    .duration(300)
                    .attr('r', nodeToCluster[nodeId] !== undefined ? 28 : 24)
                    .attr('stroke-width', 3)
                    .attr('stroke', '#FF5252');
                
                // Remove any existing labels
                const existingLabels = document.querySelectorAll('.highlighted-node-label');
                existingLabels.forEach(label => label.remove());
            }
            
            // Remove any existing notifications
            const existingNotifications = document.querySelectorAll('.graph-notification');
            existingNotifications.forEach(notif => notif.remove());
        }
    }
}

// Functions for similar pairs sorting and filtering
function filterSimilarPairs(query) {
    const originalQuery = query || '';
    query = (originalQuery || '').toLowerCase().trim();
    const normalizedQuery = normalizeText(query);
    
    console.log("Filtering similar pairs with query:", query);
    console.log("Normalized query:", normalizedQuery);
    
    const container = document.getElementById('similar-pairs-container');
    if (!container) {
        console.error("Similar pairs container not found");
        return;
    }
    
    const pairs = container.querySelectorAll('.similar-pair');
    console.log(`Found ${pairs.length} similar pairs to search`);
    let visibleCount = 0;
    
    // First, remove any existing highlights
    container.querySelectorAll('.role-link .highlight').forEach(el => {
        const parent = el.parentNode;
        if (parent && parent.hasAttribute('data-original-text')) {
            parent.textContent = parent.getAttribute('data-original-text');
        }
    });
    
    pairs.forEach((pair, index) => {
        let hasMatch = false;
        
        // Check for empty query
        if (query === '') {
            hasMatch = true;
        } else {
            const combinedNames = pair.getAttribute('data-combined-names') || '';
            
            // Check each role link individually for matches
            const roleLinks = pair.querySelectorAll('.role-link');
            console.log(`Pair ${index + 1} has ${roleLinks.length} role links`);
            
            roleLinks.forEach(link => {
                // Store original text if not already stored
                if (!link.hasAttribute('data-original-text')) {
                    link.setAttribute('data-original-text', link.textContent || '');
                }
                
                const originalText = link.getAttribute('data-original-text') || '';
                const lowerText = originalText.toLowerCase();
                const normalizedText = normalizeText(originalText);
                
                // Check for exact match first (case insensitive)
                if (lowerText === query) {
                    console.log(`Exact match found in role: "${originalText}"`);
                    hasMatch = true;
                    
                    // Highlight the entire text
                    link.innerHTML = `<span class="highlight">${originalText}</span>`;
                }
                // Then check for normalized match
                else if (normalizedQuery && normalizedText.includes(normalizedQuery)) {
                    console.log(`Normalized match found in role: "${originalText}"`);
                    hasMatch = true;
                    
                    // Create highlighted version of text based on original query
                    let highlightedText = '';
                    let lastIndex = 0;
                    let startIndex = lowerText.indexOf(query);
                    
                    // If direct substring match found
                    if (startIndex !== -1) {
                        while (startIndex !== -1) {
                            // Add text before match
                            highlightedText += originalText.substring(lastIndex, startIndex);
                            
                            // Add highlighted match
                            highlightedText += '<span class="highlight">' + 
                                originalText.substring(startIndex, startIndex + query.length) + 
                                '</span>';
                            
                            // Move to next potential match
                            lastIndex = startIndex + query.length;
                            startIndex = lowerText.indexOf(query, lastIndex);
                        }
                        
                        // Add remaining text
                        highlightedText += originalText.substring(lastIndex);
                    } 
                    // If only normalized match found, highlight the whole text
                    else {
                        highlightedText = `<span class="highlight">${originalText}</span>`;
                    }
                    
                    // Set the new HTML
                    link.innerHTML = highlightedText;
                }
                // Finally check for partial match in original text
                else if (query && lowerText.includes(query)) {
                    console.log(`Partial match found in role: "${originalText}"`);
                    hasMatch = true;
                    
                    // Create highlighted version of text
                    let highlightedText = '';
                    let lastIndex = 0;
                    let startIndex = lowerText.indexOf(query);
                    
                    while (startIndex !== -1) {
                        // Add text before match
                        highlightedText += originalText.substring(lastIndex, startIndex);
                        
                        // Add highlighted match
                        highlightedText += '<span class="highlight">' + 
                            originalText.substring(startIndex, startIndex + query.length) + 
                            '</span>';
                        
                        // Move to next potential match
                        lastIndex = startIndex + query.length;
                        startIndex = lowerText.indexOf(query, lastIndex);
                    }
                    
                    // Add remaining text
                    highlightedText += originalText.substring(lastIndex);
                    
                    // Set the new HTML
                    link.innerHTML = highlightedText;
                }
            });
            
            // If no match found in role links, check the combined names attribute as a fallback
            if (!hasMatch && combinedNames.includes(query)) {
                hasMatch = true;
            }
        }
        
        if (hasMatch) {
            pair.classList.remove('filtered');
            visibleCount++;
        } else {
            pair.classList.add('filtered');
        }
    });
    
    console.log(`Found ${visibleCount} matching pairs`);
    
    // Show a message if no results
    let noResultsMsg = container.querySelector('.no-filter-results');
    
    if (visibleCount === 0) {
        if (!noResultsMsg) {
            noResultsMsg = document.createElement('div');
            noResultsMsg.className = 'no-filter-results';
            noResultsMsg.textContent = 'No matching role pairs found.';
            container.appendChild(noResultsMsg);
        }
    } else if (noResultsMsg) {
        noResultsMsg.remove();
    }
}

function clearSimilarPairsFilter() {
    const filterInput = document.getElementById('similar-pairs-filter');
    if (filterInput) {
        filterInput.value = '';
        filterSimilarPairs('');
    }
}

function sortSimilarPairs(sortBy) {
    const container = document.getElementById('similar-pairs-container');
    if (!container) return;
    
    const pairs = Array.from(container.querySelectorAll('.similar-pair'));
    
    // Sort the pairs based on the selected criteria
    pairs.sort((a, b) => {
        switch (sortBy) {
            case 'similarity-desc':
                return parseFloat(b.getAttribute('data-similarity')) - parseFloat(a.getAttribute('data-similarity'));
            case 'similarity-asc':
                return parseFloat(a.getAttribute('data-similarity')) - parseFloat(b.getAttribute('data-similarity'));
            case 'name-asc':
                return a.getAttribute('data-source-name').localeCompare(b.getAttribute('data-source-name'));
            case 'name-desc':
                return b.getAttribute('data-source-name').localeCompare(a.getAttribute('data-source-name'));
            default:
                return 0;
        }
    });
    
    // Reappend the sorted pairs to the container
    pairs.forEach(pair => {
        container.appendChild(pair);
    });
    
    // Preserve the current filter
    const filterInput = document.getElementById('similar-pairs-filter');
    if (filterInput && filterInput.value) {
        filterSimilarPairs(filterInput.value);
    }
}

// Function to initialize button text based on content visibility
function initializeButtonText() {
    // Graph view button
    const graphContainer = document.getElementById('similarity-graph-canvas-container');
    const graphButton = document.querySelector('button[onclick="toggleGraphView()"]');
    if (graphContainer && graphButton) {
        graphButton.textContent = graphContainer.classList.contains('hidden') ? 'Show Graph' : 'Hide Graph';
    }
    
    // Clusters button
    const clustersSection = document.getElementById('similarity-clusters');
    const clustersButton = document.querySelector('.clusters-button');
    if (clustersSection && clustersButton) {
        clustersButton.textContent = clustersSection.classList.contains('hidden') ? 'Show Clusters' : 'Hide Clusters';
    }
}

// Add a helper function to normalize text for searching
function normalizeText(text) {
    if (!text) return '';
    return text.toLowerCase()
        .replace(/[^\w\s-]/g, '') // Remove special characters except spaces and hyphens
        .replace(/\s+/g, ' ')     // Normalize whitespace
        .trim();
}

function filterClusters(query) {
    const originalQuery = query || '';
    query = (originalQuery || '').toLowerCase().trim();
    const normalizedQuery = normalizeText(query);
    
    console.log("Filtering clusters with query:", query);
    console.log("Normalized query:", normalizedQuery);
    
    const tableBody = document.getElementById('clusters-table-body');
    if (!tableBody) {
        console.error("Clusters table body not found");
        return;
    }
    
    const rows = tableBody.querySelectorAll('.cluster-row');
    console.log(`Found ${rows.length} cluster rows to search`);
    let visibleCount = 0;
    
    // First, remove any existing highlights
    document.querySelectorAll('.role-link .highlight').forEach(el => {
        const parent = el.parentNode;
        if (parent && parent.hasAttribute('data-original-text')) {
            parent.textContent = parent.getAttribute('data-original-text');
        }
    });
    
    rows.forEach((row, index) => {
        let hasMatch = false;
        let exactMatch = false;
        
        // Check for empty query
        if (query === '') {
            hasMatch = true;
        } else {
            // Check each role link individually for matches
            const roleLinks = row.querySelectorAll('.role-link');
            console.log(`Cluster ${index + 1} has ${roleLinks.length} role links`);
            
            roleLinks.forEach(link => {
                // Store original text if not already stored
                if (!link.hasAttribute('data-original-text')) {
                    link.setAttribute('data-original-text', link.textContent || '');
                }
                
                const originalText = link.getAttribute('data-original-text') || '';
                const lowerText = originalText.toLowerCase();
                const normalizedText = normalizeText(originalText);
                
                // Check for exact match first (case insensitive)
                if (lowerText === query) {
                    console.log(`Exact match found in role: "${originalText}"`);
                    hasMatch = true;
                    exactMatch = true;
                    
                    // Highlight the entire text
                    link.innerHTML = `<span class="highlight">${originalText}</span>`;
                }
                // Then check for normalized match
                else if (normalizedQuery && normalizedText.includes(normalizedQuery)) {
                    console.log(`Normalized match found in role: "${originalText}"`);
                    hasMatch = true;
                    
                    // Create highlighted version of text based on original query
                    let highlightedText = '';
                    let lastIndex = 0;
                    let startIndex = lowerText.indexOf(query);
                    
                    // If direct substring match found
                    if (startIndex !== -1) {
                        while (startIndex !== -1) {
                            // Add text before match
                            highlightedText += originalText.substring(lastIndex, startIndex);
                            
                            // Add highlighted match
                            highlightedText += '<span class="highlight">' + 
                                originalText.substring(startIndex, startIndex + query.length) + 
                                '</span>';
                            
                            // Move to next potential match
                            lastIndex = startIndex + query.length;
                            startIndex = lowerText.indexOf(query, lastIndex);
                        }
                        
                        // Add remaining text
                        highlightedText += originalText.substring(lastIndex);
                    } 
                    // If only normalized match found, highlight the whole text
                    else {
                        highlightedText = `<span class="highlight">${originalText}</span>`;
                    }
                    
                    // Set the new HTML
                    link.innerHTML = highlightedText;
                }
                // Finally check for partial match in original text
                else if (query && lowerText.includes(query)) {
                    console.log(`Partial match found in role: "${originalText}"`);
                    hasMatch = true;
                    
                    // Create highlighted version of text
                    let highlightedText = '';
                    let lastIndex = 0;
                    let startIndex = lowerText.indexOf(query);
                    
                    while (startIndex !== -1) {
                        // Add text before match
                        highlightedText += originalText.substring(lastIndex, startIndex);
                        
                        // Add highlighted match
                        highlightedText += '<span class="highlight">' + 
                            originalText.substring(startIndex, startIndex + query.length) + 
                            '</span>';
                        
                        // Move to next potential match
                        lastIndex = startIndex + query.length;
                        startIndex = lowerText.indexOf(query, lastIndex);
                    }
                    
                    // Add remaining text
                    highlightedText += originalText.substring(lastIndex);
                    
                    // Set the new HTML
                    link.innerHTML = highlightedText;
                }
            });
        }
        
        if (hasMatch) {
            row.classList.remove('filtered');
            visibleCount++;
        } else {
            row.classList.add('filtered');
        }
    });
    
    console.log(`Found ${visibleCount} matching clusters`);
    
    // Show a message if no results
    let noResultsMsg = tableBody.parentNode.querySelector('.no-filter-results');
    
    if (visibleCount === 0) {
        if (!noResultsMsg) {
            noResultsMsg = document.createElement('div');
            noResultsMsg.className = 'no-filter-results';
            noResultsMsg.textContent = 'No matching clusters found.';
            tableBody.parentNode.appendChild(noResultsMsg);
        }
    } else if (noResultsMsg) {
        noResultsMsg.remove();
    }
}

function clearClustersFilter() {
    const filterInput = document.getElementById('clusters-filter');
    if (filterInput) {
        filterInput.value = '';
        filterClusters('');
    }
}

// Functions for invalid actions filtering
function filterInvalidActions(query) {
    const originalQuery = query || '';
    query = (originalQuery || '').toLowerCase().trim();
    const normalizedQuery = normalizeText(query);
    
    console.log("Filtering invalid actions with query:", query);
    console.log("Normalized query:", normalizedQuery);
    
    const container = document.getElementById('invalid-actions-container');
    if (!container) {
        console.error("Invalid actions container not found");
        return;
    }
    
    const items = container.querySelectorAll('.invalid-action-item');
    console.log(`Found ${items.length} invalid action items to search`);
    let visibleCount = 0;
    
    // First, remove any existing highlights
    container.querySelectorAll('.invalid-action-pill .highlight').forEach(el => {
        const parent = el.parentNode;
        if (parent && parent.hasAttribute('data-original-text')) {
            parent.textContent = parent.getAttribute('data-original-text');
        }
    });
    
    items.forEach((item, index) => {
        let hasMatch = false;
        
        // Check for empty query
        if (query === '') {
            hasMatch = true;
        } else {
            const roleName = item.getAttribute('data-role-name') || '';
            const actions = item.getAttribute('data-actions') || '';
            
            // Check if the role name or actions contain the query
            if (roleName.includes(query) || actions.includes(query)) {
                hasMatch = true;
                
                // Highlight matching text in role name
                const roleLink = item.querySelector('.role-link');
                if (roleLink) {
                    if (!roleLink.hasAttribute('data-original-text')) {
                        roleLink.setAttribute('data-original-text', roleLink.textContent || '');
                    }
                    
                    const originalText = roleLink.getAttribute('data-original-text') || '';
                    const lowerText = originalText.toLowerCase();
                    
                    if (lowerText.includes(query)) {
                        let highlightedText = '';
                        let lastIndex = 0;
                        let startIndex = lowerText.indexOf(query);
                        
                        while (startIndex !== -1) {
                            // Add text before match
                            highlightedText += originalText.substring(lastIndex, startIndex);
                            
                            // Add highlighted match
                            highlightedText += '<span class="highlight">' + 
                                originalText.substring(startIndex, startIndex + query.length) + 
                                '</span>';
                            
                            // Move to next potential match
                            lastIndex = startIndex + query.length;
                            startIndex = lowerText.indexOf(query, lastIndex);
                        }
                        
                        // Add remaining text
                        highlightedText += originalText.substring(lastIndex);
                        
                        // Set the new HTML
                        roleLink.innerHTML = highlightedText;
                    }
                }
                
                // Highlight matching text in action pills
                const actionPills = item.querySelectorAll('.invalid-action-pill');
                actionPills.forEach(pill => {
                    if (!pill.hasAttribute('data-original-text')) {
                        pill.setAttribute('data-original-text', pill.textContent || '');
                    }
                    
                    const originalText = pill.getAttribute('data-original-text') || '';
                    const lowerText = originalText.toLowerCase();
                    
                    if (lowerText.includes(query)) {
                        let highlightedText = '';
                        let lastIndex = 0;
                        let startIndex = lowerText.indexOf(query);
                        
                        while (startIndex !== -1) {
                            // Add text before match
                            highlightedText += originalText.substring(lastIndex, startIndex);
                            
                            // Add highlighted match
                            highlightedText += '<span class="highlight">' + 
                                originalText.substring(startIndex, startIndex + query.length) + 
                                '</span>';
                            
                            // Move to next potential match
                            lastIndex = startIndex + query.length;
                            startIndex = lowerText.indexOf(query, lastIndex);
                        }
                        
                        // Add remaining text
                        highlightedText += originalText.substring(lastIndex);
                        
                        // Set the new HTML
                        pill.innerHTML = highlightedText;
                    }
                });
            }
        }
        
        if (hasMatch) {
            item.classList.remove('filtered');
            visibleCount++;
        } else {
            item.classList.add('filtered');
        }
    });
    
    console.log(`Found ${visibleCount} matching invalid action items`);
    
    // Show a message if no results
    let noResultsMsg = container.querySelector('.no-filter-results');
    
    if (visibleCount === 0) {
        if (!noResultsMsg) {
            noResultsMsg = document.createElement('div');
            noResultsMsg.className = 'no-filter-results';
            noResultsMsg.textContent = 'No matching invalid actions found.';
            container.appendChild(noResultsMsg);
        }
    } else if (noResultsMsg) {
        noResultsMsg.remove();
    }
}

function clearInvalidActionsFilter() {
    const filterInput = document.getElementById('invalid-actions-filter');
    if (filterInput) {
        filterInput.value = '';
        filterInvalidActions('');
    }
}

// Add event listener for invalid actions filter
document.addEventListener('DOMContentLoaded', function() {
    const invalidActionsFilter = document.getElementById('invalid-actions-filter');
    if (invalidActionsFilter) {
        invalidActionsFilter.addEventListener('input', function() {
            filterInvalidActions(this.value);
        });
    }
});
