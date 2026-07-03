import { useState } from 'react';
import {
  createKpResponseForm,
  createOfferInvoiceForm,
  createReceiveForm,
  createShipmentForm,
  createSupplierInviteForm,
  createSupplyRequestForm,
} from './supplyInitialForms';

export function useSupplyWorkflowState() {
  const [supplyTab, setSupplyTab] = useState('inbox');
  const [showSupplyForm, setShowSupplyForm] = useState(false);
  const [newSupplyReq, setNewSupplyReq] = useState(createSupplyRequestForm);
  const [supplyExpandedId, setSupplyExpandedId] = useState(null);
  const [supplyStockCheck, setSupplyStockCheck] = useState(null);
  const [supplyAiText, setSupplyAiText] = useState('');
  const [supplyAiLoading, setSupplyAiLoading] = useState(false);
  const [supplyRejectId, setSupplyRejectId] = useState(null);
  const [supplyRejectReason, setSupplyRejectReason] = useState('');
  const [supplyCollapsedProjects, setSupplyCollapsedProjects] = useState({});
  const [showRequestKpModal, setShowRequestKpModal] = useState(null);
  const [suggestedSuppliers, setSuggestedSuppliers] = useState(null);
  const [selectedSupplierIds, setSelectedSupplierIds] = useState([]);
  const [requestKpLoading, setRequestKpLoading] = useState(false);
  const [respondingOfferId, setRespondingOfferId] = useState(null);
  const [newKpResponse, setNewKpResponse] = useState(createKpResponseForm);
  const [compareResultByReq, setCompareResultByReq] = useState({});
  const [compareLoadingReqId, setCompareLoadingReqId] = useState(null);
  const [invoicingOfferId, setInvoicingOfferId] = useState(null);
  const [newOfferInvoice, setNewOfferInvoice] = useState(createOfferInvoiceForm);
  const [shippingOfferId, setShippingOfferId] = useState(null);
  const [shipmentForm, setShipmentForm] = useState(createShipmentForm);
  const [receivingDeliveryId, setReceivingDeliveryId] = useState(null);
  const [receiveForm, setReceiveForm] = useState(createReceiveForm);
  const [deliveryAiResultById, setDeliveryAiResultById] = useState({});
  const [deliveryAiLoadingId, setDeliveryAiLoadingId] = useState(null);
  const [showSupplierInviteModal, setShowSupplierInviteModal] = useState(false);
  const [supplierInviteForm, setSupplierInviteForm] = useState(createSupplierInviteForm);
  const [generatedInviteLink, setGeneratedInviteLink] = useState(null);

  return {
    compareLoadingReqId,
    compareResultByReq,
    deliveryAiLoadingId,
    deliveryAiResultById,
    generatedInviteLink,
    invoicingOfferId,
    newKpResponse,
    newOfferInvoice,
    newSupplyReq,
    receiveForm,
    receivingDeliveryId,
    requestKpLoading,
    respondingOfferId,
    selectedSupplierIds,
    setCompareLoadingReqId,
    setCompareResultByReq,
    setDeliveryAiLoadingId,
    setDeliveryAiResultById,
    setGeneratedInviteLink,
    setInvoicingOfferId,
    setNewKpResponse,
    setNewOfferInvoice,
    setNewSupplyReq,
    setReceiveForm,
    setReceivingDeliveryId,
    setRequestKpLoading,
    setRespondingOfferId,
    setSelectedSupplierIds,
    setShipmentForm,
    setShippingOfferId,
    setShowRequestKpModal,
    setShowSupplierInviteModal,
    setShowSupplyForm,
    setSuggestedSuppliers,
    setSupplierInviteForm,
    setSupplyAiLoading,
    setSupplyAiText,
    setSupplyCollapsedProjects,
    setSupplyExpandedId,
    setSupplyRejectId,
    setSupplyRejectReason,
    setSupplyStockCheck,
    setSupplyTab,
    shipmentForm,
    shippingOfferId,
    showRequestKpModal,
    showSupplierInviteModal,
    showSupplyForm,
    suggestedSuppliers,
    supplierInviteForm,
    supplyAiLoading,
    supplyAiText,
    supplyCollapsedProjects,
    supplyExpandedId,
    supplyRejectId,
    supplyRejectReason,
    supplyStockCheck,
    supplyTab,
  };
}
