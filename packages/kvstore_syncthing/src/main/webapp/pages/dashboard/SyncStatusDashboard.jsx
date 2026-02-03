/**
 * ===============================================================================
 * PROVENANCE TRACKING
 * ===============================================================================
 * File: packages/kvstore_syncthing/src/main/webapp/pages/dashboard/SyncStatusDashboard.jsx
 * Created: 2026-02-03
 * Author: Claude (AI Assistant - claude-opus-4-5-20251101)
 * Session: claude/kvstore-sync-solution-vPJQI
 * Type: React Dashboard Component
 *
 * Change History:
 * -------------------------------------------------------------------------------
 * Date        Author      Type    Description
 * -------------------------------------------------------------------------------
 * 2026-02-03  Claude/AI   CREATE  Main sync status dashboard using Splunk-UI
 *                                 components exclusively per SDK requirements.
 * -------------------------------------------------------------------------------
 *
 * License: MIT
 * ===============================================================================
 */

import React, { useState, useEffect, useCallback } from 'react';
import layout from '@splunk/react-page';
import { SplunkThemeProvider } from '@splunk/themes';

// Splunk-UI Components - NO external UI libraries
import Card from '@splunk/react-ui/Card';
import CardLayout from '@splunk/react-ui/CardLayout';
import Heading from '@splunk/react-ui/Heading';
import Table from '@splunk/react-ui/Table';
import Button from '@splunk/react-ui/Button';
import ControlGroup from '@splunk/react-ui/ControlGroup';
import Message from '@splunk/react-ui/Message';
import WaitSpinner from '@splunk/react-ui/WaitSpinner';
import Link from '@splunk/react-ui/Link';
import Tooltip from '@splunk/react-ui/Tooltip';
import Modal from '@splunk/react-ui/Modal';
import TabLayout from '@splunk/react-ui/TabLayout';
import DefinitionList from '@splunk/react-ui/DefinitionList';
import CollapsiblePanel from '@splunk/react-ui/CollapsiblePanel';
import Badge from '@splunk/react-ui/Badge';
import Paginator from '@splunk/react-ui/Paginator';

// Splunk-UI Icons - NO external icon libraries
import CheckCircle from '@splunk/react-icons/CheckCircle';
import Error from '@splunk/react-icons/Error';
import Warning from '@splunk/react-icons/Warning';
import Refresh from '@splunk/react-icons/Refresh';
import Clock from '@splunk/react-icons/Clock';
import Play from '@splunk/react-icons/Play';
import Pause from '@splunk/react-icons/Pause';
import Info from '@splunk/react-icons/Info';
import Settings from '@splunk/react-icons/Settings';

// Splunk utilities
import { createRESTURL } from '@splunk/splunk-utils/url';
import { defaultFetchInit, handleResponse, handleError } from '@splunk/splunk-utils/fetch';

/**
 * Status badge component using Splunk-UI Badge
 */
const StatusBadge = ({ status }) => {
    const statusConfig = {
        ok: { appearance: 'success', icon: <CheckCircle />, label: 'In Sync' },
        syncing: { appearance: 'info', icon: <WaitSpinner />, label: 'Syncing' },
        warning: { appearance: 'warning', icon: <Warning />, label: 'Warning' },
        error: { appearance: 'error', icon: <Error />, label: 'Error' },
        pending: { appearance: 'default', icon: <Clock />, label: 'Pending' },
    };

    const config = statusConfig[status] || statusConfig.pending;

    return (
        <Badge appearance={config.appearance}>
            {config.icon} {config.label}
        </Badge>
    );
};

/**
 * Destination status card component
 */
const DestinationStatusCard = ({ destination, onRefresh, onViewDetails }) => {
    return (
        <Card>
            <Card.Header title={destination.name}>
                <Tooltip content="View destination details">
                    <Button
                        appearance="secondary"
                        icon={<Info />}
                        onClick={() => onViewDetails(destination)}
                    />
                </Tooltip>
            </Card.Header>
            <Card.Body>
                <DefinitionList>
                    <DefinitionList.Term>Status</DefinitionList.Term>
                    <DefinitionList.Description>
                        <StatusBadge status={destination.status} />
                    </DefinitionList.Description>

                    <DefinitionList.Term>Type</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.destination_type}
                    </DefinitionList.Description>

                    <DefinitionList.Term>Host</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.host}:{destination.port}
                    </DefinitionList.Description>

                    <DefinitionList.Term>Last Sync</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.last_sync || 'Never'}
                    </DefinitionList.Description>

                    <DefinitionList.Term>Records Synced</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.records_synced?.toLocaleString() || '0'}
                    </DefinitionList.Description>
                </DefinitionList>
            </Card.Body>
            <Card.Footer>
                <Button
                    appearance="primary"
                    icon={<Refresh />}
                    onClick={() => onRefresh(destination.name)}
                    label="Sync Now"
                />
            </Card.Footer>
        </Card>
    );
};

/**
 * Sync jobs table component
 */
const SyncJobsTable = ({ jobs, onRunJob, onToggleJob }) => {
    const [currentPage, setCurrentPage] = useState(0);
    const pageSize = 10;

    const columns = [
        { key: 'name', label: 'Job Name' },
        { key: 'destination', label: 'Destination' },
        { key: 'profile', label: 'Profile' },
        { key: 'status', label: 'Status' },
        { key: 'last_run', label: 'Last Run' },
        { key: 'next_run', label: 'Next Run' },
        { key: 'actions', label: 'Actions' },
    ];

    const paginatedJobs = jobs.slice(
        currentPage * pageSize,
        (currentPage + 1) * pageSize
    );

    return (
        <>
            <Table stripeRows>
                <Table.Head>
                    {columns.map((col) => (
                        <Table.HeadCell key={col.key}>{col.label}</Table.HeadCell>
                    ))}
                </Table.Head>
                <Table.Body>
                    {paginatedJobs.map((job) => (
                        <Table.Row key={job.name}>
                            <Table.Cell>{job.name}</Table.Cell>
                            <Table.Cell>{job.destination}</Table.Cell>
                            <Table.Cell>{job.profile}</Table.Cell>
                            <Table.Cell>
                                <StatusBadge status={job.status} />
                            </Table.Cell>
                            <Table.Cell>{job.last_run || 'Never'}</Table.Cell>
                            <Table.Cell>{job.next_run || 'Not scheduled'}</Table.Cell>
                            <Table.Cell>
                                <Button
                                    appearance="secondary"
                                    icon={<Play />}
                                    onClick={() => onRunJob(job.name)}
                                    disabled={job.status === 'syncing'}
                                />
                                <Button
                                    appearance="secondary"
                                    icon={job.disabled ? <Play /> : <Pause />}
                                    onClick={() => onToggleJob(job.name)}
                                />
                            </Table.Cell>
                        </Table.Row>
                    ))}
                </Table.Body>
            </Table>
            {jobs.length > pageSize && (
                <Paginator
                    current={currentPage}
                    onChange={(e, { page }) => setCurrentPage(page)}
                    totalPages={Math.ceil(jobs.length / pageSize)}
                />
            )}
        </>
    );
};

/**
 * Integrity verification panel
 */
const IntegrityPanel = ({ integrityData, onRunVerification }) => {
    return (
        <CollapsiblePanel title="Data Integrity Verification" defaultOpen>
            {integrityData.overall_status && (
                <Message
                    type={
                        integrityData.overall_status === 'ok'
                            ? 'success'
                            : integrityData.overall_status === 'warning'
                            ? 'warning'
                            : 'error'
                    }
                >
                    Overall Status: {integrityData.overall_status}
                    {integrityData.last_check && ` (Last checked: ${integrityData.last_check})`}
                </Message>
            )}

            <Table stripeRows>
                <Table.Head>
                    <Table.HeadCell>Destination</Table.HeadCell>
                    <Table.HeadCell>Collection</Table.HeadCell>
                    <Table.HeadCell>Source Count</Table.HeadCell>
                    <Table.HeadCell>Dest Count</Table.HeadCell>
                    <Table.HeadCell>Checksum Match</Table.HeadCell>
                    <Table.HeadCell>Status</Table.HeadCell>
                </Table.Head>
                <Table.Body>
                    {(integrityData.results || []).map((result, idx) => (
                        <Table.Row key={idx}>
                            <Table.Cell>{result.destination}</Table.Cell>
                            <Table.Cell>{result.collection}</Table.Cell>
                            <Table.Cell>{result.source_count?.toLocaleString()}</Table.Cell>
                            <Table.Cell>{result.dest_count?.toLocaleString()}</Table.Cell>
                            <Table.Cell>
                                {result.checksum_match ? (
                                    <CheckCircle style={{ color: 'green' }} />
                                ) : (
                                    <Error style={{ color: 'red' }} />
                                )}
                            </Table.Cell>
                            <Table.Cell>
                                <StatusBadge status={result.status} />
                            </Table.Cell>
                        </Table.Row>
                    ))}
                </Table.Body>
            </Table>

            <ControlGroup label="">
                <Button
                    appearance="primary"
                    icon={<Refresh />}
                    onClick={onRunVerification}
                    label="Run Integrity Check"
                />
            </ControlGroup>
        </CollapsiblePanel>
    );
};

/**
 * Destination details modal
 */
const DestinationDetailsModal = ({ destination, open, onClose }) => {
    if (!destination) return null;

    return (
        <Modal open={open} onRequestClose={onClose}>
            <Modal.Header
                title={`Destination: ${destination.name}`}
                onRequestClose={onClose}
            />
            <Modal.Body>
                <DefinitionList>
                    <DefinitionList.Term>Name</DefinitionList.Term>
                    <DefinitionList.Description>{destination.name}</DefinitionList.Description>

                    <DefinitionList.Term>Type</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.destination_type}
                    </DefinitionList.Description>

                    <DefinitionList.Term>Host</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.host}:{destination.port}
                    </DefinitionList.Description>

                    <DefinitionList.Term>SSL</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.use_ssl ? 'Enabled' : 'Disabled'}
                    </DefinitionList.Description>

                    <DefinitionList.Term>Auth Type</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.auth_type}
                    </DefinitionList.Description>

                    <DefinitionList.Term>Target App</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.target_app}
                    </DefinitionList.Description>

                    <DefinitionList.Term>Target Owner</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.target_owner}
                    </DefinitionList.Description>

                    <DefinitionList.Term>Connection Timeout</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.connection_timeout}s
                    </DefinitionList.Description>

                    <DefinitionList.Term>Max Retries</DefinitionList.Term>
                    <DefinitionList.Description>
                        {destination.max_retries}
                    </DefinitionList.Description>
                </DefinitionList>
            </Modal.Body>
            <Modal.Footer>
                <Button appearance="secondary" onClick={onClose} label="Close" />
                <Button
                    appearance="primary"
                    to={`/app/kvstore_syncthing/configuration?tab=destinations&edit=${destination.name}`}
                    label="Edit"
                />
            </Modal.Footer>
        </Modal>
    );
};

/**
 * Main Sync Status Dashboard Component
 */
const SyncStatusDashboard = () => {
    // State
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [destinations, setDestinations] = useState([]);
    const [syncJobs, setSyncJobs] = useState([]);
    const [integrityData, setIntegrityData] = useState({});
    const [selectedDestination, setSelectedDestination] = useState(null);
    const [detailsModalOpen, setDetailsModalOpen] = useState(false);

    /**
     * Fetch data from Splunk REST API using splunk-utils
     */
    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            // Fetch destinations
            const destUrl = createRESTURL('kvstore_syncthing_destinations');
            const destResponse = await fetch(destUrl, {
                ...defaultFetchInit,
                method: 'GET',
            });
            const destData = await handleResponse(destResponse);
            setDestinations(destData.entry?.map((e) => e.content) || []);

            // Fetch sync jobs
            const jobsUrl = createRESTURL('kvstore_syncthing_kvstore_sync_job');
            const jobsResponse = await fetch(jobsUrl, {
                ...defaultFetchInit,
                method: 'GET',
            });
            const jobsData = await handleResponse(jobsResponse);
            setSyncJobs(jobsData.entry?.map((e) => ({ ...e.content, name: e.name })) || []);

            // Fetch integrity status
            const integrityUrl = createRESTURL('kvstore_syncthing_integrity_status');
            const integrityResponse = await fetch(integrityUrl, {
                ...defaultFetchInit,
                method: 'GET',
            });
            const integrityResult = await handleResponse(integrityResponse);
            setIntegrityData(integrityResult.entry?.[0]?.content || {});
        } catch (err) {
            setError(handleError(err));
        } finally {
            setLoading(false);
        }
    }, []);

    /**
     * Run sync for a destination
     */
    const handleSyncNow = async (destinationName) => {
        try {
            const url = createRESTURL('kvstore_syncthing_sync_now');
            await fetch(url, {
                ...defaultFetchInit,
                method: 'POST',
                body: JSON.stringify({ destination: destinationName }),
            });
            // Refresh data after triggering sync
            await fetchData();
        } catch (err) {
            setError(`Failed to trigger sync: ${err.message}`);
        }
    };

    /**
     * Run a specific sync job
     */
    const handleRunJob = async (jobName) => {
        try {
            const url = createRESTURL('kvstore_syncthing_run_job');
            await fetch(url, {
                ...defaultFetchInit,
                method: 'POST',
                body: JSON.stringify({ job: jobName }),
            });
            await fetchData();
        } catch (err) {
            setError(`Failed to run job: ${err.message}`);
        }
    };

    /**
     * Toggle job enabled/disabled
     */
    const handleToggleJob = async (jobName) => {
        try {
            const url = createRESTURL(`kvstore_syncthing_kvstore_sync_job/${jobName}`);
            const job = syncJobs.find((j) => j.name === jobName);
            await fetch(url, {
                ...defaultFetchInit,
                method: 'POST',
                body: JSON.stringify({ disabled: !job.disabled }),
            });
            await fetchData();
        } catch (err) {
            setError(`Failed to toggle job: ${err.message}`);
        }
    };

    /**
     * Run integrity verification
     */
    const handleRunIntegrityCheck = async () => {
        try {
            const url = createRESTURL('kvstore_syncthing_verify_integrity');
            await fetch(url, {
                ...defaultFetchInit,
                method: 'POST',
            });
            await fetchData();
        } catch (err) {
            setError(`Failed to run integrity check: ${err.message}`);
        }
    };

    /**
     * View destination details
     */
    const handleViewDetails = (destination) => {
        setSelectedDestination(destination);
        setDetailsModalOpen(true);
    };

    // Fetch data on mount
    useEffect(() => {
        fetchData();
        // Set up auto-refresh every 30 seconds
        const interval = setInterval(fetchData, 30000);
        return () => clearInterval(interval);
    }, [fetchData]);

    // Loading state
    if (loading && destinations.length === 0) {
        return (
            <div style={{ textAlign: 'center', padding: '40px' }}>
                <WaitSpinner size="large" />
                <p>Loading sync status...</p>
            </div>
        );
    }

    return (
        <SplunkThemeProvider family="enterprise" colorScheme="light">
            <div style={{ padding: '20px' }}>
                <Heading level={1}>KVStore Syncthing Dashboard</Heading>

                {error && (
                    <Message type="error" onRequestRemove={() => setError(null)}>
                        {error}
                    </Message>
                )}

                <ControlGroup label="" style={{ marginBottom: '20px' }}>
                    <Button
                        appearance="secondary"
                        icon={<Refresh />}
                        onClick={fetchData}
                        label="Refresh"
                    />
                    <Button
                        appearance="secondary"
                        icon={<Settings />}
                        to="/app/kvstore_syncthing/configuration"
                        label="Configuration"
                    />
                </ControlGroup>

                <TabLayout defaultActivePanelId="overview">
                    <TabLayout.Panel label="Overview" panelId="overview">
                        <Heading level={2}>Sync Destinations</Heading>
                        <CardLayout>
                            {destinations.map((dest) => (
                                <DestinationStatusCard
                                    key={dest.name}
                                    destination={dest}
                                    onRefresh={handleSyncNow}
                                    onViewDetails={handleViewDetails}
                                />
                            ))}
                        </CardLayout>

                        {destinations.length === 0 && (
                            <Message type="info">
                                No destinations configured.{' '}
                                <Link to="/app/kvstore_syncthing/configuration?tab=destinations">
                                    Add a destination
                                </Link>
                            </Message>
                        )}
                    </TabLayout.Panel>

                    <TabLayout.Panel label="Sync Jobs" panelId="jobs">
                        <Heading level={2}>Sync Jobs</Heading>
                        {syncJobs.length > 0 ? (
                            <SyncJobsTable
                                jobs={syncJobs}
                                onRunJob={handleRunJob}
                                onToggleJob={handleToggleJob}
                            />
                        ) : (
                            <Message type="info">
                                No sync jobs configured.{' '}
                                <Link to="/app/kvstore_syncthing/inputs?service=kvstore_sync_job">
                                    Create a sync job
                                </Link>
                            </Message>
                        )}
                    </TabLayout.Panel>

                    <TabLayout.Panel label="Data Integrity" panelId="integrity">
                        <Heading level={2}>Data Integrity</Heading>
                        <IntegrityPanel
                            integrityData={integrityData}
                            onRunVerification={handleRunIntegrityCheck}
                        />
                    </TabLayout.Panel>
                </TabLayout>

                <DestinationDetailsModal
                    destination={selectedDestination}
                    open={detailsModalOpen}
                    onClose={() => setDetailsModalOpen(false)}
                />
            </div>
        </SplunkThemeProvider>
    );
};

// Mount to Splunk page
layout(<SyncStatusDashboard />, { pageTitle: 'Sync Status Dashboard' });

export default SyncStatusDashboard;
