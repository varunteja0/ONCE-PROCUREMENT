import AppLayout from '@/components/AppLayout';
import ProtectedRoute from '@/components/ProtectedRoute';
import { lazy, Suspense, type ReactNode } from 'react';
import {
    createBrowserRouter,
    Navigate,
    type RouteObject,
} from 'react-router-dom';
// --- L3.3 cockpit ---
import CockpitLayout from '@/components/CockpitLayout';
import CockpitProtectedRoute from '@/components/CockpitProtectedRoute';
// --- /L3.3 cockpit ---
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';

const Login = lazy(() => import('@/pages/Login'));
const Register = lazy(() => import('@/pages/Register'));
const Dashboard = lazy(() => import('@/pages/Dashboard'));
const Submissions = lazy(() => import('@/pages/Submissions'));
const SubmissionNew = lazy(() => import('@/pages/SubmissionNew'));
const SubmissionDetail = lazy(() => import('@/pages/SubmissionDetail'));
const Suppliers = lazy(() => import('@/pages/Suppliers'));
const SupplierDetail = lazy(() => import('@/pages/SupplierDetail'));
const Receipts = lazy(() => import('@/pages/Receipts'));
const ReceiptDetail = lazy(() => import('@/pages/ReceiptDetail'));
const Portals = lazy(() => import('@/pages/Portals'));
const ConsentLedger = lazy(() => import('@/pages/ConsentLedger'));
const Settings = lazy(() => import('@/pages/Settings'));
const Cois = lazy(() => import('@/pages/Cois'));
const LossRuns = lazy(() => import('@/pages/LossRuns'));
const ProducerLicenses = lazy(() => import('@/pages/ProducerLicenses'));
const EoCertificates = lazy(() => import('@/pages/EoCertificates'));
const AcordForms = lazy(() => import('@/pages/AcordForms'));
const RiskSchedules = lazy(() => import('@/pages/RiskSchedules'));
const VerifierKeys = lazy(() => import('@/pages/VerifierKeys'));
const NotFound = lazy(() => import('@/pages/NotFound'));

// --- L3.7 imports ---
const ImportList = lazy(() => import('@/pages/imports/ImportList'));
const ImportNew = lazy(() => import('@/pages/imports/ImportNew'));
const ImportDetail = lazy(() => import('@/pages/imports/ImportDetail'));
// --- /L3.7 imports ---

// --- L3.9 inbound ---
const InboundList = lazy(() => import('@/pages/inbound/InboundList'));
const InboundDetail = lazy(() => import('@/pages/inbound/InboundDetail'));
const InboundRoutingRules = lazy(() => import('@/pages/inbound/RoutingRules'));
// --- /L3.9 inbound ---

// --- L3.10 audit ---
const AuditLogPage = lazy(() => import('@/pages/audit/AuditLog'));
const AuditDetailPage = lazy(() => import('@/pages/audit/AuditDetail'));
const AuditExportsPage = lazy(() => import('@/pages/audit/AuditExports'));
// --- /L3.10 audit ---

// --- L3.5 billing ---
const Pricing = lazy(() => import('@/pages/Pricing'));
const Billing = lazy(() => import('@/pages/Billing'));
const CheckoutSuccess = lazy(() => import('@/pages/CheckoutSuccess'));
const CheckoutCancel = lazy(() => import('@/pages/CheckoutCancel'));
// --- /L3.5 billing ---

// --- L3.6 onboarding ---
const OnboardingWizard = lazy(() => import('@/pages/onboarding/Wizard'));
const OnboardingSignup = lazy(() => import('@/pages/onboarding/StepSignup'));
const OnboardingVerifyEmail = lazy(() => import('@/pages/onboarding/StepVerifyEmail'));
const OnboardingProfile = lazy(() => import('@/pages/onboarding/StepCompanyProfile'));
const OnboardingPlan = lazy(() => import('@/pages/onboarding/StepChoosePlan'));
const OnboardingPortal = lazy(() => import('@/pages/onboarding/StepConnectPortal'));
const OnboardingSupplier = lazy(() => import('@/pages/onboarding/StepAddSupplier'));
const OnboardingSubmission = lazy(() => import('@/pages/onboarding/StepFirstSubmission'));
const OnboardingDone = lazy(() => import('@/pages/onboarding/StepDone'));
// --- /L3.6 onboarding ---

// --- L3.3 cockpit ---
const CockpitLogin = lazy(() => import('@/pages/cockpit/Login'));
const CockpitDashboard = lazy(() => import('@/pages/cockpit/Dashboard'));
const CockpitTenantList = lazy(() => import('@/pages/cockpit/TenantList'));
const CockpitTenantDetail = lazy(() => import('@/pages/cockpit/TenantDetail'));
const CockpitOperateAs = lazy(() => import('@/pages/cockpit/OperateAs'));
const CockpitAuditLog = lazy(() => import('@/pages/cockpit/AuditLog'));
const CockpitAccount = lazy(() => import('@/pages/cockpit/Account'));
// --- /L3.3 cockpit ---

function PageFallback(): JSX.Element {
  return (
    <div className="space-y-3 p-6" aria-busy="true" role="status" aria-label="Loading page">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function RouteError(): JSX.Element {
  return (
    <div className="p-6">
      <ErrorState
        title="This page failed to load"
        description="Reload the page to try again. If the problem persists, contact support."
        onRetry={() => window.location.reload()}
      />
    </div>
  );
}

function wrap(element: ReactNode): JSX.Element {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageFallback />}>{element}</Suspense>
    </ErrorBoundary>
  );
}

export const routes: RouteObject[] = [
  {
    path: '/login',
    element: wrap(<Login />),
    errorElement: <RouteError />,
  },
  {
    path: '/register',
    element: wrap(<Register />),
    errorElement: <RouteError />,
  },
  // --- L3.5 billing ---
  {
    path: '/pricing',
    element: wrap(<Pricing />),
    errorElement: <RouteError />,
  },
  // --- /L3.5 billing ---
  // --- L3.6 onboarding ---
  { path: '/onboarding', element: wrap(<OnboardingWizard />), errorElement: <RouteError /> },
  { path: '/onboarding/signup', element: wrap(<OnboardingSignup />), errorElement: <RouteError /> },
  { path: '/onboarding/verify-email', element: wrap(<OnboardingVerifyEmail />), errorElement: <RouteError /> },
  { path: '/onboarding/profile', element: wrap(<OnboardingProfile />), errorElement: <RouteError /> },
  { path: '/onboarding/plan', element: wrap(<OnboardingPlan />), errorElement: <RouteError /> },
  { path: '/onboarding/portal', element: wrap(<OnboardingPortal />), errorElement: <RouteError /> },
  { path: '/onboarding/supplier', element: wrap(<OnboardingSupplier />), errorElement: <RouteError /> },
  { path: '/onboarding/submission', element: wrap(<OnboardingSubmission />), errorElement: <RouteError /> },
  { path: '/onboarding/done', element: wrap(<OnboardingDone />), errorElement: <RouteError /> },
  // --- /L3.6 onboarding ---
  {
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    errorElement: <RouteError />,
    children: [
      { path: '/', element: <Navigate to="/dashboard" replace /> },
      { path: '/dashboard', element: wrap(<Dashboard />) },
      { path: '/submissions', element: wrap(<Submissions />) },
      { path: '/submissions/new', element: wrap(<SubmissionNew />) },
      { path: '/submissions/:id', element: wrap(<SubmissionDetail />) },
      { path: '/suppliers', element: wrap(<Suppliers />) },
      { path: '/suppliers/:id', element: wrap(<SupplierDetail />) },
      { path: '/receipts', element: wrap(<Receipts />) },
      { path: '/receipts/:id', element: wrap(<ReceiptDetail />) },
      { path: '/portals', element: wrap(<Portals />) },
      { path: '/consent-ledger', element: wrap(<ConsentLedger />) },
      { path: '/cois', element: wrap(<Cois />) },
      { path: '/loss-runs', element: wrap(<LossRuns />) },
      { path: '/producer-licenses', element: wrap(<ProducerLicenses />) },
      { path: '/eo-certificates', element: wrap(<EoCertificates />) },
      { path: '/acord-forms', element: wrap(<AcordForms />) },
      { path: '/risk-schedules', element: wrap(<RiskSchedules />) },
      { path: '/settings', element: wrap(<Settings />) },
      // --- L6.1 verifier API keys ---
      { path: '/verifier-keys', element: wrap(<VerifierKeys />) },
      // --- /L6.1 verifier API keys ---
      // --- L3.7 imports ---
      { path: '/imports', element: wrap(<ImportList />) },
      { path: '/imports/new', element: wrap(<ImportNew />) },
      { path: '/imports/:id', element: wrap(<ImportDetail />) },
      // --- /L3.7 imports ---
      // --- L3.9 inbound ---
      { path: '/inbound', element: wrap(<InboundList />) },
      { path: '/inbound/rules', element: wrap(<InboundRoutingRules />) },
      { path: '/inbound/:id', element: wrap(<InboundDetail />) },
      // --- /L3.9 inbound ---
      // --- L3.10 audit ---
      { path: '/audit', element: wrap(<AuditLogPage />) },
      { path: '/audit/exports', element: wrap(<AuditExportsPage />) },
      { path: '/audit/:id', element: wrap(<AuditDetailPage />) },
      // --- /L3.10 audit ---
      // --- L3.5 billing ---
      { path: '/billing', element: wrap(<Billing />) },
      { path: '/billing/success', element: wrap(<CheckoutSuccess />) },
      { path: '/billing/cancel', element: wrap(<CheckoutCancel />) },
      // --- /L3.5 billing ---
    ],
  },
  // --- L3.3 cockpit ---
  {
    path: '/cockpit/login',
    element: wrap(<CockpitLogin />),
    errorElement: <RouteError />,
  },
  {
    element: (
      <CockpitProtectedRoute>
        <CockpitLayout />
      </CockpitProtectedRoute>
    ),
    errorElement: <RouteError />,
    children: [
      { path: '/cockpit', element: wrap(<CockpitDashboard />) },
      { path: '/cockpit/tenants', element: wrap(<CockpitTenantList />) },
      { path: '/cockpit/tenants/:tenantId', element: wrap(<CockpitTenantDetail />) },
      { path: '/cockpit/operate-as', element: wrap(<CockpitOperateAs />) },
      { path: '/cockpit/audit', element: wrap(<CockpitAuditLog />) },
      { path: '/cockpit/account', element: wrap(<CockpitAccount />) },
    ],
  },
  // --- /L3.3 cockpit ---
  { path: '*', element: wrap(<NotFound />) },
];

export const router = createBrowserRouter(routes);
