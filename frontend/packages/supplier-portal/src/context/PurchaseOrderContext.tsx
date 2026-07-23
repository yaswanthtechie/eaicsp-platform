import { createContext, useContext, useState } from "react";
import type { PurchaseOrder } from "../types/po";
import { purchaseOrders } from "../mocks/purchaseOrders";

interface PurchaseOrderContextType {
  orders: PurchaseOrder[];
  setOrders: React.Dispatch<React.SetStateAction<PurchaseOrder[]>>;
}

const PurchaseOrderContext = createContext<PurchaseOrderContextType | undefined>(
  undefined
);

export const PurchaseOrderProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [orders, setOrders] = useState<PurchaseOrder[]>(purchaseOrders);

  return (
    <PurchaseOrderContext.Provider value={{ orders, setOrders }}>
      {children}
    </PurchaseOrderContext.Provider>
  );
};

export const usePurchaseOrders = () => {
  const context = useContext(PurchaseOrderContext);

  if (!context) {
    throw new Error("usePurchaseOrders must be used inside PurchaseOrderProvider");
  }

  return context;
};