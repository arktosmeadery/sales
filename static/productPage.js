//submit
//update google sheets
//generate invoice

//get signature
//add new customer


var customerID = false;
var toPurchase = {};
productsToPurchase = {};

$(function(){
    //CLICKS
    $('#customerTable .acustomer').click(function(){
        customerID = $(this).attr('id').substr(1);
        $('#customerTable tr').removeClass('selected');
        $(this).addClass('selected');
        addCustomerToSummary(customerID);
    });

    $('#addNewCustomer').click(function(){
        customerID = 'new';
        $('#customerTable tr').removeClass('selected');
    });

    $('#productTable .aproduct').click(function(){
        $(this).addClass('selected');
        amountPopUp($(this).attr('id'), $(this).find(".stock").data('value'));
    });

    $('#submit button').click(function(){
        updateStock();
        
    });
});

function updateStock(){
   fetch('/updateStock', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ customerID: customerID, toPurchase: toPurchase  }),

    }).then(data =>{
        console.log(data);

        //TODO GENERATE INVOICE
        //generateInvoice(data['saleID'])
    })
}
function generateInvoice(saleID){
    fetch('/generateInvoice', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ saleID:saleID  }),

    }).then(data =>{
        console.log(data);

        
        
    })
}

//amount pop up to select qty
function amountPopUp(id, stock){
    //x out of pop up
    $('#amountPop').removeClass('hideit');
    $('#amountPop .close').off().click(function(){
        cancelPopUp(id, 'close');
    });

    // ok button adds product to summary, if qty selected >0, else close poopup
    $('#amountPop .ok').off().click(function(){
        if($('#popamount').val() > 0){
            var amt = $('#popamount').val();
            toPurchase[id] = amt;
            $('#'+id).children(".amountToPurchase").html(amt);
            $('#amountPop').addClass('hideit');
            addProductToSummary(id,amt)
        }else{
            cancelPopUp(id, 'zero');
        }
    });

    //cancel button closes popup
    $('#amountPop .cancel').off().click(function(){
        cancelPopUp(id, 'cancel');
    });

    //adds product info to pop up and generates select menu for current stock amount
    var prodName = $("#" + id + " .name").data("value");
    var stockAvailable = $("#" + id + " .stock").data("value");
    $('#amountPop #popname').html(prodName);
  
    $('#poptype').html($("#" + id).closest('.prodType').find('h3').first().html());
    $('#popamount').html('');
    for(var i=0;i<stockAvailable+1;i++){
        $('#popamount').append("<option value='"+i+"'>" + i + "</option>");
    }

}

//clear stok pop up, remove amount if amount reset
function cancelPopUp(id, why){
    //TODO if 0 and cancel - deselect
    $('#amountPop').addClass('hideit');
    if(why == 'zero'){
        $('#' + id).removeClass('selected');
        $('#'+ id).children(".amountToPurchase").html('');
        removeProductFromSummary(id);
    }
}

//add selected product to summary,
// remove it first, in case duplicate
// adjust total
function addProductToSummary(pid, amt){
    removeProductFromSummary(pid);
    var prodType = $("#" + pid).closest('.prodType').find('h3').first().html();
    var prodName = $("#" + pid + " .name").data("value");
    var price = $("#" + pid + " .price").data("value");

    str = "<tr class='aproduct' id='" + pid + "'>";
    str += "<td class='pname'>" + prodName + "</td>";
    str += "<td class='ptype'>" + prodType + "</td>";
    str += "<td class='pamt'>" + amt + "</td>";
    str += "<td class='price'>"+ price + "</td>";
    str += "<td class='tot'>" + (amt*price).toFixed(2) + "</td>";

    $('#productsToPurchase').append(str);
    
    adjustTotal();
}

function removeProductFromSummary(pid){
    $('#summary #' + pid).remove();
    adjustTotal();
}

//add selected customer info to invoice
function addCustomerToSummary(cid){
    var contactName = $("#c" + cid + " .contact").data("value");
    var bizName = $("#c" + cid + " .business_name").data("value"); 
    $('#activeCustomer').html(bizName);
    $('#customername').html(contactName);
    adjustTotal()
}


//adjust final total based on line items
function adjustTotal(){
    cost = 0;
    $('#productsToPurchase .tot').each(function(){
        cost += parseFloat($(this).html());
    })
    $('#invoicetotal').html(cost.toFixed(2));
    if(cost>0 && customerID){
        $('#submit .abutton').removeClass('hideit');
    }else{
        $('#submit .abutton').addClass('hideit');
    }
}