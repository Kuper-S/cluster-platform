const GITHUB_USERNAME = 'kuper-s'; // Add your GitHub username here

$(document).ready(function() {
    // Populate API server and Client server images dropdowns
    $.get('/get_images', function(data) {
        const apiImageSelect = $('#api-image');
        const clientImageSelect = $('#client-image');
        apiImageSelect.empty(); // Clear any existing options
        clientImageSelect.empty(); // Clear any existing options
        data.forEach(image => {
            apiImageSelect.append(new Option(image, image));
            clientImageSelect.append(new Option(image, image));
        });
    });

    // Fetch and display cluster information
    $.get('/cluster_info', function(data) {
        const clusterInfo = $('#cluster-info');
        clusterInfo.empty();

        // Display nodes
        const nodeTable = $('<table>').append(
            $('<thead>').append(
                $('<tr>').append(
                    $('<th>').text('Node Name'),
                    $('<th>').text('Status')
                )
            ),
            $('<tbody>')
        );
        data.nodes.forEach(node => {
            nodeTable.append(
                $('<tr>').append(
                    $('<td>').text(node.name),
                    $('<td>').text(node.status)
                )
            );
        });
        clusterInfo.append($('<h3>').text('Nodes'));
        clusterInfo.append(nodeTable);

        // Display namespaces
        const nsTable = $('<table>').append(
            $('<thead>').append(
                $('<tr>').append(
                    $('<th>').text('Namespace Name')
                )
            ),
            $('<tbody>')
        );
        data.namespaces.forEach(ns => {
            nsTable.append(
                $('<tr>').append(
                    $('<td>').text(ns.name)
                )
            );
        });
        clusterInfo.append($('<h3>').text('Namespaces'));
        clusterInfo.append(nsTable);
    });

    // Handle form submissions
    $('#deploy-form').submit(function(event) {
        event.preventDefault();
        deploy();
    });

    $('#status-form').submit(function(event) {
        event.preventDefault();
        getStatus();
    });

    $('#delete-form').submit(function(event) {
        event.preventDefault();
        destroy();
    });
});

function deploy() {
    const apiImage = $('#api-image').val();
    const clientImage = $('#client-image').val();
    const namespace = $('#namespace').val();

    $.ajax({
        url: '/deploy',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ api_image: apiImage, client_image: clientImage, namespace: namespace }),
        success: function(response) {
            alert(response.status);
            // Optionally, refresh status or add namespace to the list
        },
        error: function(response) {
            alert(response.responseJSON.error);
        }
    });
}

function destroy() {
    const namespace = $('#delete-namespace').val();

    $.ajax({
        url: '/delete',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ namespace: namespace }),
        success: function(response) {
            alert(response.status);
            // Optionally, refresh status or remove namespace from the list
        },
        error: function(response) {
            alert(response.responseJSON.error);
        }
    });
}

function getStatus() {
    const namespace = $('#status-namespace').val();

    $.get('/status', { namespace: namespace }, function(data) {
        const statusOutput = $('#status-output');
        statusOutput.empty();
        if (data.error) {
            statusOutput.append($('<p>').text('Error: ' + data.error));
        } else {
            const table = $('<table>').append(
                $('<thead>').append(
                    $('<tr>').append(
                        $('<th>').text('Pod Name'),
                        $('<th>').text('Status'),
                        $('<th>').text('Link')
                    )
                ),
                $('<tbody>')
            );
            data.forEach(pod => {
                table.append(
                    $('<tr>').append(
                        $('<td>').text(pod.name),
                        $('<td>').text(pod.status),
                        $('<td>').append($('<a>').attr('href', `http://client.example.com/${namespace}`).attr('target', '_blank').text('Open'))
                    )
                );
            });
            statusOutput.append(table);
        }
    }).fail(function(response) {
        alert(response.responseJSON.error);
    });
}
