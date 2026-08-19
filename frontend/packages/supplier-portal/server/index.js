const { ApolloServer } = require("@apollo/server");
const { startStandaloneServer } = require("@apollo/server/standalone");

const purchaseOrders = [
  {
    po_number: "PO1001",
    supplier_id: "SUP001",
    status: "draft",
    total_amount: 25000,
    expected_delivery: "2026-08-01",
    items: [
      {
        sku: "SKU001",
        product_name: "Laptop",
        quantity: 2,
        unit_price: 10000,
      },
      {
        sku: "SKU002",
        product_name: "Mouse",
        quantity: 10,
        unit_price: 500,
      },
    ],
  },

  {
    po_number: "PO1002",
    supplier_id: "SUP001",
    status: "sent",
    total_amount: 18000,
    expected_delivery: "2026-08-05",
    items: [
      {
        sku: "SKU003",
        product_name: "Keyboard",
        quantity: 6,
        unit_price: 1000,
      },
      {
        sku: "SKU004",
        product_name: "Monitor",
        quantity: 2,
        unit_price: 6000,
      },
    ],
  },

  {
    po_number: "PO1003",
    supplier_id: "SUP002",
    status: "sent",
    total_amount: 9500,
    expected_delivery: "2026-08-08",
    items: [
      {
        sku: "SKU005",
        product_name: "Printer",
        quantity: 1,
        unit_price: 7000,
      },
      {
        sku: "SKU006",
        product_name: "USB Cable",
        quantity: 10,
        unit_price: 250,
      },
    ],
  },

  {
    po_number: "PO1004",
    supplier_id: "SUP003",
    status: "acknowledged",
    total_amount: 21000,
    expected_delivery: "2026-08-10",
    items: [
      {
        sku: "SKU007",
        product_name: "Scanner",
        quantity: 2,
        unit_price: 8000,
      },
      {
        sku: "SKU008",
        product_name: "Web Camera",
        quantity: 5,
        unit_price: 1000,
      },
    ],
  },

  {
    po_number: "PO1005",
    supplier_id: "SUP004",
    status: "acknowledged",
    total_amount: 14500,
    expected_delivery: "2026-08-15",
    items: [
      {
        sku: "SKU009",
        product_name: "SSD",
        quantity: 5,
        unit_price: 2500,
      },
      {
        sku: "SKU010",
        product_name: "HDMI Cable",
        quantity: 10,
        unit_price: 200,
      },
    ],
  },

{
  po_number: "PO1006",
  supplier_id: "SUP005",
  status: "fulfilled",
  total_amount: 30000,
  expected_delivery: "2026-07-20",
  items: [
    {
      sku: "SKU011",
      product_name: "Desktop PC",
      quantity: 3,
      unit_price: 10000,
    },
    {
      sku: "SKU014",
      product_name: "Keyboard",
      quantity: 5,
      unit_price: 500,
    },
  ],
},

{
  po_number: "PO1007",
  supplier_id: "SUP006",
  status: "fulfilled",
  total_amount: 9000,
  expected_delivery: "2026-07-22",
  items: [
    {
      sku: "SKU012",
      product_name: "Router",
      quantity: 3,
      unit_price: 3000,
    },
    {
      sku: "SKU015",
      product_name: "Network Cable",
      quantity: 10,
      unit_price: 100,
    },
  ],
},
{
  po_number: "PO1008",
  supplier_id: "SUP007",
  status: "cancelled",
  total_amount: 12000,
  expected_delivery: "2026-08-25",
  items: [
    {
      sku: "SKU013",
      product_name: "Projector",
      quantity: 1,
      unit_price: 12000,
    },
    {
      sku: "SKU016",
      product_name: "Projector Stand",
      quantity: 2,
      unit_price: 1000,
    },
  ],
},


];

const invoices = [];

const typeDefs = `#graphql

type POItem{

sku:String!

product_name:String!

quantity:Int!

unit_price:Int!

}


type PurchaseOrder{

po_number:String!

supplier_id:String!

status:String!

total_amount:Int!

expected_delivery:String!

items:[POItem!]!

}
type Invoice{

invoiceNumber:String!

poReference:String!

amount:Int!

date:String!

}

type PurchaseOrderEdge {
  cursor: String!
  node: PurchaseOrder!
}

type PageInfo {
  hasNextPage: Boolean!
  endCursor: String
}

type PurchaseOrderConnection {
  edges: [PurchaseOrderEdge!]!
  pageInfo: PageInfo!
}

type Query {
  purchaseOrders(
    first: Int!
    after: String

    poNumber: String
    status: String
    minAmount: Int
    maxAmount: Int

    startDate: String
    endDate: String

  ): PurchaseOrderConnection!
}

type Mutation{

acknowledgePurchaseOrder(
po_number:String!
):PurchaseOrder

submitInvoice(
invoiceNumber:String!
poReference:String!
amount:Int!
date:String!
):Invoice!

}

`;

const resolvers = {

Query: {
  purchaseOrders(
    _,
    {
      first,
      after,
      poNumber,
      status,
      minAmount,
      maxAmount,
      startDate,
      endDate,
    }
  ) {
    let filteredOrders = [...purchaseOrders];

    // Filter by PO Number
    if (poNumber) {
      filteredOrders = filteredOrders.filter((po) =>
        po.po_number.toLowerCase().includes(poNumber.toLowerCase())
      );
    }

    // Filter by Status
    if (status) {
      filteredOrders = filteredOrders.filter(
        (po) => po.status.toLowerCase() === status.toLowerCase()
      );
    }

    // Filter by Amount
    if (minAmount != null) {
      filteredOrders = filteredOrders.filter(
        (po) => po.total_amount >= minAmount
      );
    }

    if (maxAmount != null) {
      filteredOrders = filteredOrders.filter(
        (po) => po.total_amount <= maxAmount
      );
    }

    // Filter by Date
    if (startDate) {
      filteredOrders = filteredOrders.filter(
        (po) => po.expected_delivery >= startDate
      );
    }

    if (endDate) {
      filteredOrders = filteredOrders.filter(
        (po) => po.expected_delivery <= endDate
      );
    }

    let startIndex = 0;

    if (after) {
      startIndex =
        filteredOrders.findIndex(
          (po) => po.po_number === after
        ) + 1;
    }

    const items = filteredOrders.slice(
      startIndex,
      startIndex + first
    );

    const edges = items.map((po) => ({
      cursor: po.po_number,
      node: po,
    }));

    const endCursor =
      edges.length > 0
        ? edges[edges.length - 1].cursor
        : null;

    const hasNextPage =
      startIndex + first < filteredOrders.length;

    return {
      edges,
      pageInfo: {
        hasNextPage,
        endCursor,
      },
    };
  },
},

Mutation: {

  acknowledgePurchaseOrder(_, { po_number }) {

    const order = purchaseOrders.find(
      (po) => po.po_number === po_number
    );

    if (!order) {
      throw new Error("Purchase Order not found");
    }

    if (order.status !== "sent") {
      throw new Error(
        "Only sent purchase orders can be acknowledged"
      );
    }

    order.status = "acknowledged";

    return order;
  },

  submitInvoice(
    _,
    {
      invoiceNumber,
      poReference,
      amount,
      date,
    }
  ) {

    const invoice = {
      invoiceNumber,
      poReference,
      amount,
      date,
    };

    invoices.push(invoice);

    return invoice;
  },

},

};

const server = new ApolloServer({

typeDefs,

resolvers,

});

const PORT = process.env.PORT || 4000;

startStandaloneServer(server, {
  listen: { port: PORT },
}).then(({ url }) => {
  console.log(`Server Ready at ${url}`);
});



